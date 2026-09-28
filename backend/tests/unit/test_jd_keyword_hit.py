"""JD 命中率脚本纯函数单测（M4 PR-R2）：关键词匹配 / 命中率 / 聚合 / 边界。"""
from __future__ import annotations

from eval.scripts.jd_keyword_hit import aggregate, evaluate_questions, keyword_match, load_samples


def _must(name, keywords):
    return {"name": name, "category": "hard_skill", "keywords": keywords, "importance": "must"}


def _q(content, points=None):
    return {"content": content, "reference_points": points or []}


def test_keyword_match_substring_case_insensitive():
    assert keyword_match("使用 Kafka 集群", "kafka") is True


def test_keyword_match_chinese_substring():
    assert keyword_match("谈谈分布式系统设计", "分布式") is True


def test_keyword_match_prefix():
    assert keyword_match("掌握分布式系统", "分布") is True


def test_keyword_match_no_hit():
    assert keyword_match("熟悉前端开发", "Kafka") is False


def test_keyword_match_empty():
    assert keyword_match("文本", "") is False


def test_evaluate_questions_all_hit():
    caps = [_must("Kafka", ["Kafka"]), _must("缓存", ["Redis"])]
    qs = [_q("使用 Kafka 与 Redis 缓存")]
    result = evaluate_questions(qs, caps)
    assert result["must_total"] == 2
    assert result["must_hit"] == 2
    assert result["hit_rate"] == 1.0


def test_evaluate_questions_partial_hit():
    caps = [_must("Kafka", ["Kafka"]), _must("Go", ["Go 语言"])]
    qs = [_q("使用 Kafka")]
    result = evaluate_questions(qs, caps)
    assert result["must_hit"] == 1
    assert result["hit_rate"] == 0.5
    assert result["misses"] == ["Go"]


def test_evaluate_questions_zero_must():
    caps = [{"name": "加分项", "category": "x", "keywords": ["k"], "importance": "nice_to_have"}]
    result = evaluate_questions([_q("题")], caps)
    assert result["must_total"] == 0
    assert result["hit_rate"] is None


def test_evaluate_questions_matches_reference_points():
    caps = [_must("Kafka", ["Kafka"])]
    qs = [_q("题目正文", points=["Kafka 消息可靠性"])]
    assert evaluate_questions(qs, caps)["must_hit"] == 1


def test_aggregate():
    per = [
        {"must_total": 2, "must_hit": 2},
        {"must_total": 2, "must_hit": 1},
    ]
    result = aggregate(per)
    assert result["must_total"] == 4
    assert result["must_hit"] == 3
    assert result["hit_rate"] == 0.75


def test_load_samples(tmp_path):
    import json

    path = tmp_path / "golden.jsonl"
    path.write_text(
        json.dumps({"position": "后端", "capabilities": []}) + "\n\nnot-json\n" +
        json.dumps({"position": "前端", "capabilities": []}) + "\n",
        encoding="utf-8",
    )
    samples = load_samples(path)
    assert len(samples) == 2
    assert samples[0]["position"] == "后端"
