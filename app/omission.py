"""脱文（漏抄）审计：在 ``/api/assemble`` 的拼接稿与独立参照转写间定位漏字接缝。

提交与 :func:`app.assembler.assemble` 相同的有序 segments 与一份独立参照转写
reference（1～840 字），先复用其拼接得到拼接文本与逐字来源（沿用段数/长度
限制与续接失败规则），再枚举“在某一处接缝补入参照稿连续缺文”的方案，供人工
复核拼接稿是否在段间接缝处漏抄了字。

**接缝候选**只取拼接稿相邻两字（``text[k-1]`` 与 ``text[k]``）之间，且沿
逐字来源满足：左字的来源中含某原始段 ``s``，右字的来源中不含 ``s``，却含
某个**更晚**的原始段 ``t > s``——即段 ``s`` 在此处退出而更晚的段已经接上。

**参照稿长度**须比拼接稿恰好多 :data:`MIN_GAP`～:data:`MAX_GAP`（1～40）字；
差值 ``d`` 即缺文长度。对每个接缝候选 ``k`` 只枚举一种补法：把参照稿连续片段
``reference[k:k+d]`` 补在拼接稿位置 ``k``，使两稿逐位对齐：

- ``i < k``：``text[i]`` 对 ``reference[i]``；
- 补入的 ``d`` 字只在参照稿一侧，不计异字；
- ``i >= k``：``text[i]`` 对 ``reference[i+d]``。

每对字符：相同字、或任一侧为 ``?`` 记 0，双方皆为已知异字记 1；整稿异字数
不超过 :data:`MAX_MISMATCHES`（2）的方案才合格。取异字数最少的方案：唯一时
返回插入位置、缺文字串、异字数及接缝两侧的字与逐字 sources；不同接缝并列时
抛出 :class:`OmissionTieError`（接口层转为 409）；无合格方案抛出
:class:`OmissionNotFoundError`（422）。参照稿长度差不合要求抛出
:class:`OmissionRequirementError`（422）。

本模块只做审计建议，绝不改写拼接文本。
"""

from __future__ import annotations

from .aligner import WILDCARD
from .assembler import assemble

MAX_REFERENCE_LEN = 840  # 参照转写最大长度
MIN_GAP = 1              # 参照稿须比拼接稿多的最少字数
MAX_GAP = 40             # 参照稿须比拼接稿多的最多字数
MAX_MISMATCHES = 2       # 补文对齐后整稿允许的最多异字数


class OmissionRequirementError(ValueError):
    """参照稿与拼接稿的长度差不在 1～40 字之间。"""


class OmissionNotFoundError(ValueError):
    """不存在异字数不超过 :data:`MAX_MISMATCHES` 的补文方案。"""


class OmissionTieError(ValueError):
    """异字数最少的补文方案由多个不同接缝并列取得，无法唯一确定。"""

    def __init__(self, mismatches: int, plans: list[dict]):
        self.mismatches = mismatches
        self.plans = plans
        super().__init__(
            f"异字数最少的补文方案有 {len(plans)} 个不同接缝并列（异字数 "
            f"{mismatches}），无法唯一确定"
        )


def _pair_mismatch(a: str, b: str) -> int:
    """单对字符的异字计数：相同字或任一侧为 ``?`` 记 0，已知异字记 1。"""
    if a == WILDCARD or b == WILDCARD:
        return 0
    return 0 if a == b else 1


def find_seams(sources: list[list[dict]]) -> list[int]:
    """找出全部脱文接缝候选位置 ``k``（插入点，1～n-1）。

    接缝在相邻两字 ``text[k-1]``、``text[k]`` 之间：存在原始段 ``s`` 使左字
    来源含 ``s``、右字来源不含 ``s``，且右字来源含某个更晚原始段 ``t > s``。
    """
    seams: list[int] = []
    for k in range(1, len(sources)):
        left_segs = {s["segment"] for s in sources[k - 1]}
        right_segs = {s["segment"] for s in sources[k]}
        if any(
            s in left_segs
            and s not in right_segs
            and any(t > s for t in right_segs)
            for s in left_segs
        ):
            seams.append(k)
    return seams


def _prefix_costs(text: str, reference: str) -> list[int]:
    """``pre[k]`` = ``text[:k]`` 与 ``reference[:k]`` 逐位对齐的异字数。

    长度为 ``n + 1``：调用处参照稿比拼接稿长（``len(reference) >= n``）。
    """
    pre = [0]
    cost = 0
    for i in range(len(text)):
        cost += _pair_mismatch(text[i], reference[i])
        pre.append(cost)
    return pre


def audit_omission(segments: list[str], reference: str) -> dict:
    """审计拼接稿相对参照稿的接缝脱文。

    返回唯一最优方案时的 ``{"text", "reference", "insert_pos", "missing",
    "mismatches", "seam"}``；拼接阶段失败原样抛出
    :class:`~app.assembler.AssemblyError`，长度差不合要求抛出
    :class:`OmissionRequirementError`，无合格方案抛出
    :class:`OmissionNotFoundError`，多接缝并列抛出 :class:`OmissionTieError`。
    """
    if not 1 <= len(reference) <= MAX_REFERENCE_LEN:
        raise ValueError(f"参照稿长度需为 1～{MAX_REFERENCE_LEN} 字")

    result = assemble(segments)
    text, sources = result["text"], result["sources"]
    n, rn = len(text), len(reference)
    gap = rn - n
    if not MIN_GAP <= gap <= MAX_GAP:
        raise OmissionRequirementError(
            f"参照稿（{rn} 字）须比拼接稿（{n} 字）恰好多 {MIN_GAP}～"
            f"{MAX_GAP} 字，当前多 {gap} 字"
        )

    seams = find_seams(sources)
    if not seams:
        raise OmissionNotFoundError(
            "拼接稿中没有符合条件的接缝：需要相邻两字中左字来源含某原始段、"
            "右字不含该段且含更晚原始段"
        )

    # 前缀异字（i < k 时 text[i] 对 reference[i]）；后缀异字（i >= k 时
    # text[i] 对 reference[i+gap]），两者均与接缝位置无关，预先一次性算好。
    pre = _prefix_costs(text, reference)

    # suf[k] = sum_{i>=k} mismatch(text[i], reference[i+gap])：补入 gap 字后，
    # 接缝右侧的拼接字 text[i] 与参照稿的 reference[i+gap] 逐位配对。
    suf = [0] * (n + 1)
    cost = 0
    for i in range(n - 1, -1, -1):
        cost += _pair_mismatch(text[i], reference[i + gap])
        suf[i] = cost

    def make_plan(k: int, mismatches: int) -> dict:
        return {
            "insert_pos": k,
            "missing": reference[k : k + gap],
            "mismatches": mismatches,
            "seam": {
                "left": {
                    "pos": k - 1,
                    "char": text[k - 1],
                    "sources": [dict(src) for src in sources[k - 1]],
                },
                "right": {
                    "pos": k,
                    "char": text[k],
                    "sources": [dict(src) for src in sources[k]],
                },
            },
        }

    plans: list[dict] = []
    best = MAX_MISMATCHES + 1
    for k in seams:
        mismatches = pre[k] + suf[k]
        if mismatches > MAX_MISMATCHES:
            continue
        if mismatches < best:
            best = mismatches
            plans = [make_plan(k, mismatches)]
        elif mismatches == best:
            plans.append(make_plan(k, mismatches))

    if not plans:
        floor = min(pre[k] + suf[k] for k in seams)
        raise OmissionNotFoundError(
            f"枚举全部 {len(seams)} 个接缝后，没有一处补入参照稿连续缺文能使整稿"
            f"异字数不超过 {MAX_MISMATCHES}（最小异字数为 {floor}），无合格方案"
        )

    plans.sort(key=lambda p: (p["insert_pos"], p["missing"]))
    if len(plans) > 1:
        raise OmissionTieError(best, plans)

    return {"text": text, "reference": reference, **plans[0]}
