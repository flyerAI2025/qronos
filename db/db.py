"""
数据库模型定义模块

该模块定义了量化交易框架管理系统的所有数据库模型和配置。
使用SQLAlchemy ORM框架，支持SQLite数据库。

主要功能：
1. 数据库连接和会话管理
2. 用户认证信息存储
3. 框架状态跟踪
4. 框架配置管理

数据库表结构：
- user: 用户认证和凭据信息
- framework_status: 框架下载和运行状态
- framework_config: 框架配置参数

"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from utils.constant import DB_PATH
from utils.log_kit import get_logger

# 初始化日志记录器
logger = get_logger()

# 创建数据库引擎
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)

# 创建会话工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# 创建声明式基类
Base = declarative_base()


class User(Base):
    """
    用户表模型
    
    存储用户的认证信息和API凭据。
    支持Google Authenticator 2FA认证和XBX API集成。
    
    :ivar id: 用户主键ID
    :vartype id: int
    :ivar uuid: XBX系统用户UUID，用于API调用
    :vartype uuid: str
    :ivar apikey: XBX系统API密钥，用于获取访问token
    :vartype apikey: str
    :ivar xbx_token: XBX系统访问token，用于API认证
    :vartype xbx_token: str
    :ivar token: 本系统JWT token，用于Web认证
    :vartype token: str
    :ivar secret: Google Authenticator密钥，用于2FA验证
    :vartype secret: str
    
    Note:
        - uuid和apikey来自XBX系统，用于第三方API调用
        - xbx_token是临时访问令牌，会定期刷新
        - token是本系统的JWT令牌，用于Web界面认证
        - secret是Google Authenticator的密钥，用于双因子认证
    """
    __tablename__ = 'user'
    
    id = Column(Integer, primary_key=True, index=True, comment="用户主键ID")
    uuid = Column(String(64), unique=True, comment="XBX系统用户UUID")
    apikey = Column(String(128), comment="XBX系统API密钥")
    xbx_token = Column(String(256), comment="XBX系统访问token")
    token = Column(String(256), comment="本系统JWT token")
    secret = Column(String(64), unique=True, comment="Google Authenticator密钥")


class FrameworkStatus(Base):
    """
    框架状态表模型
    
    跟踪所有框架的下载状态、运行状态和基本信息。
    用于监控框架的生命周期管理。
    
    :ivar id: 状态记录主键ID
    :vartype id: int
    :ivar framework_id: 框架唯一标识符
    :vartype framework_id: str
    :ivar framework_name: 框架显示名称
    :vartype framework_name: str
    :ivar status: 框架当前状态（下载中/已完成/失败等）
    :vartype status: str
    :ivar type: 框架类型（数据中心/策略框架等）
    :vartype type: str
    :ivar time: 框架版本时间戳
    :vartype time: str
    :ivar path: 框架在本地磁盘的存储路径
    :vartype path: str
    
    状态枚举值：
        - not_downloaded: 未下载
        - downloading: 下载中
        - finished: 下载完成
        - failed: 下载失败
        
    框架类型：
        - data_center: 数据中心框架
        - strategy: 策略框架
    """
    __tablename__ = 'framework_status'
    
    id = Column(Integer, primary_key=True, index=True, comment="状态记录主键ID")
    framework_id = Column(String(64), nullable=False, comment="框架唯一标识符")
    framework_name = Column(String(64), nullable=False, comment="框架显示名称")
    status = Column(String(32), nullable=False, comment="框架当前状态")
    type = Column(String(32), nullable=False, comment="框架类型")
    time = Column(String(32), nullable=False, comment="框架版本时间戳")
    path = Column(String(256), comment="框架本地存储路径")


def init_db():
    """
    初始化数据库表结构
    
    创建所有定义的数据库表。如果表已存在则跳过创建。
    该函数通常在应用启动时调用一次。
    
    Process:
        1. 检查数据库连接
        2. 根据模型定义创建表结构
        3. 记录初始化结果
        
    Note:
        - 使用create_all方法，只创建不存在的表
        - 不会删除或修改已存在的表结构
        - 如需修改表结构，建议使用数据库迁移工具
    """
    try:
        logger.info("开始初始化数据库表结构...")
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表结构初始化完成")
        
        # 记录创建的表信息
        table_names = [table.name for table in Base.metadata.tables.values()]
        logger.info(f"已创建/验证的数据库表: {', '.join(table_names)}")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
