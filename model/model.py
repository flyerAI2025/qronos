from typing import Optional, Any, List

from pydantic import BaseModel

from model.enum_kit import StatusEnum, AccountTypeEnum


class LoginRequest(BaseModel):
    google_secret_key: Optional[str] = None  # 首次登录时必传
    code: str


class ResponseModel(BaseModel):
    msg: str = "success"
    code: int = 200
    data: Optional[Any] = None

    @classmethod
    def ok(cls, data: Any = None, msg: str = "success", code: int = 200):
        return cls(msg=msg, code=code, data=data)

    @classmethod
    def error(cls, msg: str = "error", code: int = 400):
        return cls(msg=msg, code=code, data=None)


class UseApiModel(BaseModel):
    kline: bool = False
    coin_cap: bool = False


class DataCenterCfgModel(BaseModel):
    id: str
    kline_count_1h: int
    error_webhook_url: str
    use_api: UseApiModel
    data_api_uuid: Optional[str] = None
    data_api_key: Optional[str] = None
    enabled_hour_offsets: list
    funding_rate: bool = True
    is_first: bool = True


class BasicCodeStatusModel(BaseModel):
    id: str
    status: StatusEnum
    type: str
    time: str


class BasicCodeOperateModel(BaseModel):
    framework_id: str | int
    lines: int = 50
    type: str


class AccountConfigModel(BaseModel):
    account_type: AccountTypeEnum
    apiKey: Optional[str]
    secret: Optional[str]
    if_use_bnb_burn: bool = True
    buy_bnb_value: int = 11
    if_transfer_bnb: bool = True
    hour_offset: str
    wechat_webhook_url: str


class AccountModel(BaseModel):
    framework_id: str
    account_name: str
    account_config: AccountConfigModel
    get_kline_num: int = 999
    leverage: int | float = 1
    black_list: list = []
    white_list: list = []


class ApiKeySecretModel(BaseModel):
    framework_id: str
    account_name: str
    keyword: str  # apikey，secret
    total: int  # 分段总数
    sort_id: int  # 分段下标
    content: str  # 分段内容


class Pm2AppModel(BaseModel):
    name: str
    namespace: str
    script: str
    exec_interpreter: str = '~/anaconda3/envs/Alpha/bin/python'  # 默认环境
    merge_logs: bool = False
    watch: bool = False
    error_file: str
    out_file: str
    log_date_format: str = "YYYY-MM-DD HH:mm:ss.SSS Z"


class Pm2CfgModel(BaseModel):
    apps: List[Pm2AppModel]


class FrameworkCfgModel(BaseModel):
    framework_id: str
    realtime_data_path: Optional[str] = ''
    is_debug: bool = False
    error_webhook_url: str = ''
