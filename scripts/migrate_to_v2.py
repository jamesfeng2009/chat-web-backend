#!/usr/bin/env python3
"""
数据库迁移脚本 v2
应用数据库结构更改以支持新的数据结构
"""

import sys
from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.core.logger import logger


def migrate_section_level():
    """迁移Section模型中的level_hint字段为level"""
    try:
        db = SessionLocal()
        # 检查是否已经存在level字段
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sections' AND column_name = 'level'
        """)).fetchall()
        
        if not result:
            # 添加level字段
            logger.info("添加sections表的level字段")
            db.execute(text("""
                ALTER TABLE sections 
                ADD COLUMN level INTEGER 
                COMMENT '大纲层级，从1起'
            """))
            db.commit()
            
            # 复制level_hint数据到level
            logger.info("复制level_hint数据到level字段")
            db.execute(text("""
                UPDATE sections 
                SET level = level_hint 
                WHERE level_hint IS NOT NULL
            """))
            db.commit()
            
            # 删除level_hint字段
            logger.info("删除level_hint字段")
            db.execute(text("""
                ALTER TABLE sections 
                DROP COLUMN level_hint
            """))
            db.commit()
        
        db.close()
        logger.info("Section模型迁移完成")
        return True
    except Exception as e:
        logger.error(f"Section模型迁移失败: {str(e)}")
        return False


def create_paragraph_span_table():
    """创建paragraph_span表"""
    try:
        db = SessionLocal()
        
        # 检查表是否已存在
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() AND table_name = 'paragraph_spans'
        """)).fetchall()
        
        if not result:
            # 创建paragraph_span表
            logger.info("创建paragraph_span表")
            db.execute(text("""
                CREATE TABLE paragraph_spans (
                    id VARCHAR(64) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted BOOLEAN DEFAULT FALSE,
                    
                    owner_type VARCHAR(32) NOT NULL COMMENT 'Clause/ClauseItem',
                    owner_id VARCHAR(64) NOT NULL COMMENT '所属Clause或ClauseItem的ID',
                    seq INTEGER NOT NULL COMMENT '序号',
                    
                    raw_text TEXT NOT NULL COMMENT '原段',
                    style JSON COMMENT '粗体/字号/缩进/列表级',
                    loc JSON COMMENT '位置信息',
                    
                    role VARCHAR(32) DEFAULT 'NON_CLAUSE' COMMENT '角色: CLAUSE/NON_CLAUSE',
                    region VARCHAR(32) COMMENT '区域: COVER/MAIN/APPENDIX/SIGN/TOC',
                    nc_type VARCHAR(64) COMMENT '非条款类型: 详细分类',
                    content TEXT COMMENT '处理后的内容',
                    
                    INDEX idx_owner (owner_type, owner_id),
                    INDEX idx_document (owner_id, owner_type),
                    INDEX idx_region (region),
                    INDEX idx_role (role),
                    INDEX idx_nc_type (nc_type)
                )
            """))
            db.commit()
        
        db.close()
        logger.info("paragraph_span表创建完成")
        return True
    except Exception as e:
        logger.error(f"paragraph_span表创建失败: {str(e)}")
        return False


def remove_embedding_dimension():
    """移除embedding_dimension字段"""
    try:
        db = SessionLocal()
        
        # 检查clauses表是否有embedding_dimension字段
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'clauses' AND column_name = 'embedding_dimension'
        """)).fetchall()
        
        if result:
            # 删除embedding_dimension字段
            logger.info("删除clauses表的embedding_dimension字段")
            db.execute(text("""
                ALTER TABLE clauses 
                DROP COLUMN embedding_dimension
            """))
            db.commit()
        
        db.close()
        logger.info("embedding_dimension字段移除完成")
        return True
    except Exception as e:
        logger.error(f"embedding_dimension字段移除失败: {str(e)}")
        return False


def main():
    """主函数"""
    logger.info("开始数据库迁移v2")
    
    success = True
    
    # 1. 迁移Section模型
    if not migrate_section_level():
        success = False
    
    # 2. 创建paragraph_span表
    if not create_paragraph_span_table():
        success = False
    
    # 3. 移除embedding_dimension字段
    if not remove_embedding_dimension():
        success = False
    
    if success:
        logger.info("数据库迁移v2完成")
        sys.exit(0)
    else:
        logger.error("数据库迁移v2失败")
        sys.exit(1)


if __name__ == "__main__":
    main()