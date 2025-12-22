import pytest
import os
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db, Base
from app.core.config import settings

# 测试数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db() -> Generator:
    """创建测试数据库"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db) -> Generator:
    """创建测试数据库会话"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session) -> Generator:
    """创建测试客户端"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_document_content():
    """示例文档内容"""
    return {
        "title": "股权转让协议",
        "content": """
        第一条 总则
        
        1.1 本协议是关于股权转让的协议。
        
        1.2 本协议适用于股权转让的各方。
        
        第二条 股权转让
        
        2.1 甲方同意将其持有的目标公司40%股权转让给乙方。
        
        2.2 股权转让价格为人民币100万元。
        
        2.3 乙方应在本协议签署后30日内支付全部转让价款。
        
        （一）甲方权利和义务
        
        1. 甲方保证所转让的股权不存在任何权利瑕疵。
        
        2. 甲方应协助乙方办理股权变更登记手续。
        
        （二）乙方权利和义务
        
        1. 乙方应按约定支付股权转让价款。
        
        2. 乙方应承担股权变更登记的相关费用。
        
        第三条 违约责任
        
        3.1 任何一方违反本协议约定，应承担相应的违约责任。
        
        3.2 违约方应赔偿守约方因此遭受的损失。
        
        第四条 争议解决
        
        4.1 因本协议发生的争议，双方应友好协商解决。
        
        4.2 协商不成的，任何一方均有权向有管辖权的人民法院提起诉讼。
        
        第五条 其他
        
        5.1 本协议自双方签字盖章之日起生效。
        
        5.2 本协议一式两份，双方各执一份，具有同等法律效力。
        
        甲方（盖章）：
        代表签字：
        日期：2023年12月1日
        
        乙方（盖章）：
        代表签字：
        日期：2023年12月1日
        """
    }


@pytest.fixture
def sample_pdf_file():
    """创建示例PDF文件"""
    # 这里应该创建一个真实的PDF文件
    # 为了简化，返回一个模拟的文件路径
    return os.path.join(os.path.dirname(__file__), "sample.pdf")


@pytest.fixture
def sample_docx_file():
    """创建示例DOCX文件"""
    # 这里应该创建一个真实的DOCX文件
    # 为了简化，返回一个模拟的文件路径
    return os.path.join(os.path.dirname(__file__), "sample.docx")


@pytest.fixture
def sample_txt_file():
    """创建示例TXT文件"""
    # 这里应该创建一个真实的TXT文件
    # 为了简化，返回一个模拟的文件路径
    return os.path.join(os.path.dirname(__file__), "sample.txt")