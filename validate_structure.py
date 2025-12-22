#!/usr/bin/env python3
"""
验证v2格式数据结构的脚本
"""

import json
import sys


def validate_metadata(metadata: dict[str, any]) -> list[str]:
    """验证文档元数据"""
    errors = []
    
    # 必需字段检查
    if "id" not in metadata:
        errors.append("metadata中缺少必需的id字段")
    
    # 类型检查
    if "drafters" in metadata and not isinstance(metadata["drafters"], list):
        errors.append("metadata中drafters字段必须是列表类型")
    
    # 可选字段类型检查
    optional_fields = {
        "title": str,
        "type": str,
        "created_at": str,
        "file_url": str
    }
    
    for field, expected_type in optional_fields.items():
        if field in metadata and not isinstance(metadata[field], expected_type):
            errors.append(f"metadata中{field}字段必须是{expected_type.__name__}类型")
    
    return errors

def validate_structure(structure: dict[str, any], level: int = 0) -> list[str]:
    """验证文档结构数据"""
    errors = []
    
    # 必需字段检查
    if "id" not in structure:
        errors.append("  " * level + "structure中缺少必需的id字段")
    
    if "content" not in structure and "title" not in structure:
        errors.append("  " * level + "structure中必须包含content或title字段")
    
    # 类型检查
    if "children" in structure and not isinstance(structure["children"], list):
        errors.append("  " * level + "structure中children字段必须是列表类型")
    
    # 标签检查
    for tag_type in ["title_tags", "content_tags"]:
        if tag_type in structure:
            tags = structure[tag_type]
            if not isinstance(tags, dict):
                errors.append("  " * level + f"{tag_type}字段必须是字典类型")
            else:
                # 检查标签值的类型
                valid_tag_names = ["role", "region", "nc_type", "score"]
                for tag_name, tag_value in tags.items():
                    if tag_name not in valid_tag_names:
                        errors.append("  " * level + f"{tag_type}中包含无效的标签名: {tag_name}")
                    
                    if tag_name == "score" and not isinstance(tag_value, int):
                        errors.append("  " * level + f"{tag_type}中score标签必须是整数类型")
    
    # 递归检查子节点
    if "children" in structure:
        for i, child in enumerate(structure["children"]):
            child_errors = validate_structure(child, level + 1)
            errors.extend(child_errors)
    
    return errors

def validate_document(data: dict[str, any]) -> list[str]:
    """验证完整的文档数据结构"""
    errors = []
    
    # 顶级结构检查
    if "metadata" not in data:
        errors.append("数据中缺少必需的metadata字段")
    else:
        errors.extend(validate_metadata(data["metadata"]))
    
    if "structure" not in data:
        errors.append("数据中缺少必需的structure字段")
    else:
        errors.extend(validate_structure(data["structure"]))
    
    # 可选字段检查
    if "vectorization" in data and not isinstance(data["vectorization"], bool):
        errors.append("vectorization字段必须是布尔类型")
    
    return errors

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法: python validate_structure.py <json_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        errors = validate_document(data)
        
        if errors:
            print(f"发现 {len(errors)} 个错误:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("数据结构验证通过！")
            sys.exit(0)
    
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"文件不存在: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"验证过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()