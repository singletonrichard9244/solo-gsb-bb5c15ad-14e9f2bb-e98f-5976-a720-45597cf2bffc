"""脱文审计（audit_omission）测试。"""

import pytest

from app.assembler import AssemblyError
from app.omission import (
    MAX_MISMATCHES,
    MAX_REFERENCE_LEN,
    OmissionNotFoundError,
    OmissionRequirementError,
    OmissionTieError,
    audit_omission,
    find_seams,
)

SEGMENTS = ["甲乙丙丁戊己", "戊己庚辛壬癸"]
TEXT = "甲乙丙丁戊己庚辛壬癸"


def test_find_seams_only_at_segment_transition():
    # 唯一接缝在段 0 退出、段 1 仍在的相邻两字之间（己|庚，插入位置 6）
    result = audit_omission(SEGMENTS, TEXT[:6] + "朱雀" + TEXT[6:])
    assert result["text"] == TEXT
    assert result["insert_pos"] == 6
    assert result["missing"] == "朱雀"
    assert result["mismatches"] == 0
    seam = result["seam"]
    assert seam["left"] == {
        "pos": 5,
        "char": "己",
        "sources": [{"segment": 0, "pos": 5}, {"segment": 1, "pos": 1}],
    }
    assert seam["right"] == {
        "pos": 6,
        "char": "庚",
        "sources": [{"segment": 1, "pos": 2}],
    }


def test_find_seams_helper_excludes_within_segment_and_overlap():
    # 甲乙丙丁戊己 + 戊己庚辛壬癸：戊己处重叠（双源），段 0 独有的甲…己内无接缝
    from app.assembler import assemble

    sources = assemble(SEGMENTS)["sources"]
    assert find_seams(sources) == [6]
    # 完全重叠：每字来源集合相同，无接缝
    assert find_seams(assemble(["甲乙丙丁", "甲乙丙丁"])["sources"]) == []


def test_known_mismatches_counted_outside_inserted_block():
    # 参照 = 前缀含 1 个已知异字（首字 甲→X）+ 插入 1 字 + 后缀含 1 个已知异字（癸→X）
    ref = "X乙丙丁戊己" + "朱" + "庚辛壬X"
    result = audit_omission(SEGMENTS, ref)
    assert result["insert_pos"] == 6
    assert result["missing"] == "朱"
    assert result["mismatches"] == 2


def test_wildcard_pair_counts_zero():
    # 拼接稿第 3 字为 ?（由甲段 ? 与已知字补字而成），参照作 丙，记 0
    result = audit_omission(
        ["甲乙?丁戊己", "戊己庚辛壬癸"],
        "甲乙丙丁戊己" + "朱" + "庚辛壬癸",
    )
    assert result["text"][2] == "丙"
    assert result["mismatches"] == 0
    assert result["missing"] == "朱"


def test_too_many_mismatches_raises_not_found():
    # 插入块之外 3 处已知异字：超过 2
    ref = "X乙丙丁戊己" + "朱" + "庚X壬X"
    with pytest.raises(OmissionNotFoundError):
        audit_omission(SEGMENTS, ref)


def test_inserted_block_never_counted_as_mismatch():
    # 参照插入块位置上即便与右字不同也不计异字（块只在参照一侧）
    ref = "甲乙丙丁戊己" + "雀" + "庚辛壬癸"
    result = audit_omission(SEGMENTS, ref)
    assert result["mismatches"] == 0


def test_minimum_cost_plan_wins_among_seams():
    # 两个接缝都合格但异字数不同：在并列参照的“插入块”内改一个已知字。
    # k=6 时该字位于补入块（不计异字）仍为 0；k=10 时该字落到前缀对齐，异字 1。
    segments = ["甲乙丙丁戊己", "戊己庚辛庚辛", "庚辛子丑"]
    ref = "甲乙丙丁戊己" + "甲辛" + "庚辛庚辛" + "子丑"
    result = audit_omission(segments, ref)
    assert result["insert_pos"] == 6
    assert result["missing"] == "甲辛"
    assert result["mismatches"] == 0


def test_different_seams_tie_raises_tie_error():
    # 中段为周期串 庚辛庚辛：在 k=6 与 k=10 补入 庚辛 都使整稿异字 0
    segments = ["甲乙丙丁戊己", "戊己庚辛庚辛", "庚辛子丑"]
    ref = "甲乙丙丁戊己" + "庚辛" + "庚辛庚辛" + "子丑"
    with pytest.raises(OmissionTieError) as exc:
        audit_omission(segments, ref)
    assert exc.value.mismatches == 0
    positions = [p["insert_pos"] for p in exc.value.plans]
    assert positions == [6, 10]  # 按插入位置升序
    assert all(p["missing"] == "庚辛" for p in exc.value.plans)
    # 各方案带接缝两侧 sources
    assert exc.value.plans[0]["seam"]["left"]["char"] == "己"
    assert exc.value.plans[1]["seam"]["right"]["char"] == "子"


def test_no_seam_raises_not_found():
    with pytest.raises(OmissionNotFoundError):
        audit_omission(["甲乙丙丁", "甲乙丙丁"], "甲乙丙丁戊")


def test_reference_length_gap_must_be_1_to_40():
    with pytest.raises(OmissionRequirementError):
        audit_omission(SEGMENTS, TEXT)                       # 多 0 字
    with pytest.raises(OmissionRequirementError):
        audit_omission(SEGMENTS, TEXT[:-1])                  # 反而更短
    with pytest.raises(OmissionRequirementError):
        audit_omission(SEGMENTS, TEXT + "字" * 41)           # 多 41 字


def test_reference_boundary_gaps_accepted():
    # 恰好差 1 字与恰好差 40 字均通过长度门槛（是否合格另算）
    audit_omission(SEGMENTS, TEXT[:6] + "字" + TEXT[6:])
    long_ref = TEXT[:6] + "字" * 40 + TEXT[6:]
    result = audit_omission(SEGMENTS, long_ref)
    assert result["missing"] == "字" * 40
    assert result["mismatches"] == 0


def test_reference_too_long_raises_value_error():
    with pytest.raises(ValueError):
        audit_omission(SEGMENTS, "字" * (MAX_REFERENCE_LEN + 1))
    with pytest.raises(ValueError):
        audit_omission(SEGMENTS, "")


def test_assembly_gate_failure_propagates():
    with pytest.raises(AssemblyError):
        audit_omission(
            ["孔子曰未知", "未知生焉", "完全无关文本"],
            "字" * 20,
        )


def test_does_not_rewrite_assembled_text():
    # 返回的拼接文本与 /api/assemble 完全一致
    from app.assembler import assemble

    ref = TEXT[:6] + "朱雀" + TEXT[6:]
    result = audit_omission(SEGMENTS, ref)
    assert result["text"] == assemble(SEGMENTS)["text"]
    assert "朱雀" not in result["text"]
    assert result["reference"] == ref
    assert result["mismatches"] <= MAX_MISMATCHES
