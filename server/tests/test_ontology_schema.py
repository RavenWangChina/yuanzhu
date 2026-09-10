"""对象类型 DSL（YAML → JSON Schema）解析测试"""
import pytest

from yuanzhu.ontology.schema import parse_object_type_yaml


def test_parse_basic_object_type():
    """基础解析：字段提取 + JSON Schema 生成"""
    yaml_content = """
name: Bug
domain: aiqa
title_key: title
description: AIQA 测试用 Bug 类型
exposed: true
properties:
  title:
    type: string
    required: true
  status:
    type: string
    enum: [Open, InProgress, Closed]
    default: Open
  priority:
    type: integer
    minimum: 1
    maximum: 5
"""
    result = parse_object_type_yaml(yaml_content)

    assert result["name"] == "Bug"
    assert result["domain"] == "aiqa"
    assert result["title_key"] == "title"
    assert result["exposed"] is True

    schema = result["schema_json"]
    assert schema["type"] == "object"
    assert schema["properties"]["title"]["type"] == "string"
    assert schema["required"] == ["title"]
    assert schema["properties"]["status"]["enum"] == ["Open", "InProgress", "Closed"]
    assert schema["properties"]["status"]["default"] == "Open"
    assert schema["properties"]["priority"]["minimum"] == 1


def test_parse_missing_name_raises():
    """缺 name 报错"""
    with pytest.raises(ValueError, match="name"):
        parse_object_type_yaml("domain: test\nproperties: {}")


def test_parse_missing_domain_raises():
    """缺 domain 报错"""
    with pytest.raises(ValueError, match="domain"):
        parse_object_type_yaml("name: Bug\nproperties: {}")


def test_parse_empty_yaml_raises():
    """空内容报错"""
    with pytest.raises(ValueError):
        parse_object_type_yaml("")
