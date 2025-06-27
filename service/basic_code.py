import ast
from pathlib import Path
from enum import Enum


def python_repr(obj, indent=4):
    """
    将 Python 对象转换为正确的 Python 代码字符串表示
    
    与 json.dumps() 不同，这个函数会生成正确的 Python 语法：
    - 布尔值: True/False (而不是 true/false)
    - None: None (而不是 null)
    - 字符串: 使用单引号或双引号
    - 枚举类型: 使用枚举的字符串值
    
    Args:
        obj: 要转换的 Python 对象
        indent: 缩进空格数
        
    Returns:
        str: Python 代码字符串
    """
    if obj is None:
        return 'None'
    elif isinstance(obj, bool):
        return 'True' if obj else 'False'
    elif isinstance(obj, Enum):
        # 处理枚举类型：返回枚举的字符串值
        return repr(obj.value)
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, str):
        return repr(obj)
    elif isinstance(obj, list):
        if not obj:
            return '[]'
        items = [python_repr(item, indent) for item in obj]
        if len(str(obj)) < 80:  # 短列表单行显示
            return '[' + ', '.join(items) + ']'
        else:  # 长列表多行显示
            indent_str = ' ' * indent
            items_str = (',\n' + indent_str).join(items)
            return '[\n' + indent_str + items_str + '\n]'
    elif isinstance(obj, dict):
        if not obj:
            return '{}'
        items = [f'{python_repr(k, indent)}: {python_repr(v, indent)}' for k, v in obj.items()]
        if len(str(obj)) < 80:  # 短字典单行显示
            return '{' + ', '.join(items) + '}'
        else:  # 长字典多行显示
            indent_str = ' ' * indent
            items_str = (',\n' + indent_str).join(items)
            return '{\n' + indent_str + items_str + '\n}'
    else:
        # 对于其他类型，尝试使用 repr()
        return repr(obj)


def read_existing_py_file(py_path: Path):
    """
    读取现有的 Python 文件，解析其中的变量值

    Args:
        py_path: Python 文件路径

    Returns:
        dict: 解析出的变量字典
    """
    if not py_path.exists():
        return {}

    try:
        content = py_path.read_text(encoding='utf-8')
        # 使用已有的解析函数
        key_map = {
            "strategy_name": "strategy_name",
            "get_kline_num": "get_kline_num",
            "strategy_config": "strategy_config",
            "strategy_pool": "strategy_pool",
            "leverage": "leverage",
            "black_list": "black_list",
            "white_list": "white_list",
            "rebalance_mode": "rebalance_mode",
            "account_config": "account_config",
            "is_pure_long": "is_pure_long"
        }
        existing_data, _ = extract_variables_from_py(content, key_map)
        return existing_data or {}
    except Exception:
        return {}


def get_field_value(key: str, default, account_json: dict, existing_data: dict,
                    strategy_fields: list, account_fields: list):
    """
    获取字段值的工具函数

    Args:
        key: 字段名
        default: 默认值
        account_json: 账户配置 JSON
        existing_data: 现有数据
        strategy_fields: 策略相关字段列表
        account_fields: 账户相关字段列表

    Returns:
        字段值
    """
    # 策略相关字段：优先使用现有文件中的内容
    if key in strategy_fields:
        existing_value = existing_data.get(key)
        if existing_value is not None:
            return existing_value
        # 如果现有文件中没有，才使用 JSON 中的值
        json_value = account_json.get(key)
        return json_value if json_value is not None else default

    # AccountModel 字段：允许更新，但只更新非空字段
    elif key in account_fields:
        json_value = account_json.get(key)
        if json_value is not None and json_value != "":
            return json_value
        return existing_data.get(key, default)

    # 其他字段：使用默认逻辑
    else:
        json_value = account_json.get(key)
        if json_value is not None and json_value != "":
            return json_value
        return existing_data.get(key, default)


def generate_account_py_file_from_json(account_name: str, account_json: dict, accounts_dir: Path,
                                       update_mode: bool = False):
    """
    根据 account_json 生成 Python 文件（用于 basic_code_account 接口）

    Args:
        account_name: 账户名称
        account_json: 账户配置 JSON
        accounts_dir: accounts 目录路径
        update_mode: 是否为更新模式（保留已有字段）

    Returns:
        Path: 生成的 Python 文件路径
    """
    # 确保目录存在
    accounts_dir.mkdir(parents=True, exist_ok=True)
    account_py_path = accounts_dir / f'{account_name}.py'

    # 如果是更新模式，先读取现有文件
    existing_data = {}
    if update_mode:
        existing_data = read_existing_py_file(account_py_path)

    # 策略相关字段：优先使用现有文件中的内容（由 config 上传产生）
    strategy_fields = ['strategy_name', 'strategy_config', 'strategy_pool', 'rebalance_mode']

    # AccountModel 相关字段：允许更新
    account_fields = ['account_config', 'get_kline_num', 'leverage', 'black_list', 'white_list']

    # 生成 Python 文件内容
    py_content = f"""# ====================================================================================================
# ** 实盘账户配置 **
# ‼️‼️‼️账户配置，需要在accounts下的文件中做配置 ‼️‼️‼️
# 此处只是展示配置的结构，具体配置情参考 accounts 文件夹下的 _55mBTC样例.py
# 文件名就是账户名，比如 `15m大学生.py` 或者 `_55mBTC样例.py`
# ====================================================================================================
account_config = {python_repr(get_field_value('account_config', {}, account_json, existing_data, strategy_fields, account_fields))}  # 实盘账户配置

# ====================================================================================================
# ** 策略细节配置 **
# ‼️‼️‼️需要在accounts下的文件中做配置‼️‼️‼️
# 此处只是展示配置的结构，具体配置情参考 accounts 文件夹下的 _55mBTC样例.py
# ====================================================================================================
strategy_name = {python_repr(get_field_value('strategy_name', account_name, account_json, existing_data, strategy_fields, account_fields))}  # 当前账户运行策略的名称
get_kline_num = {python_repr(get_field_value('get_kline_num', 999, account_json, existing_data, strategy_fields, account_fields))}  # 获取多少根K线
strategy_config = {python_repr(get_field_value('strategy_config', {}, account_json, existing_data, strategy_fields, account_fields))}  # 策略配置
strategy_pool = {python_repr(get_field_value('strategy_pool', [], account_json, existing_data, strategy_fields, account_fields))}  # 策略池
leverage = {python_repr(get_field_value('leverage', 1, account_json, existing_data, strategy_fields, account_fields))}  # 杠杆数
black_list = {python_repr(get_field_value('black_list', [], account_json, existing_data, strategy_fields, account_fields))}  # 拉黑名单
white_list = {python_repr(get_field_value('white_list', [], account_json, existing_data, strategy_fields, account_fields))}  # 白名单
"""

    # 添加 rebalance_mode（如果存在）
    rebalance_mode = get_field_value('rebalance_mode', None, account_json, existing_data, strategy_fields,
                                     account_fields)
    if rebalance_mode is not None:
        py_content += f"rebalance_mode = {python_repr(rebalance_mode)}  # 再平衡模式\n"

    # 写入 Python 文件
    account_py_path.write_text(py_content, encoding='utf-8')
    return account_py_path


def generate_account_py_file_from_config(account_name: str, account_json: dict, extracted: dict,
                                         strategy_name_value: str, accounts_dir: Path):
    """
    根据配置文件解析结果生成 Python 文件（用于 basic_code_account_binding_strategy 接口）

    Args:
        account_name: 账户名称
        account_json: 账户配置 JSON
        extracted: 从配置文件中解析出的数据
        strategy_name_value: 策略名称
        accounts_dir: accounts 目录路径

    Returns:
        Path: 生成的 Python 文件路径
    """
    # 将 extracted 数据合并到 account_json 中
    merged_data = account_json.copy()
    merged_data.update({
        'strategy_name': strategy_name_value,
        'strategy_config': extracted.get("strategy_config"),
        'strategy_pool': extracted.get("strategy_pool"),
        'rebalance_mode': extracted.get("rebalance_mode"),
    })

    return generate_account_py_file_from_json(account_name, merged_data, accounts_dir, update_mode=False)


def ast_eval_node(node):
    """递归解析 AST 节点，支持复杂表达式"""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Str):  # Python < 3.8 兼容
        return node.s
    elif isinstance(node, ast.Num):  # Python < 3.8 兼容
        return node.n
    elif isinstance(node, ast.List):
        return [ast_eval_node(elem) for elem in node.elts]
    elif isinstance(node, ast.Dict):
        keys = [ast_eval_node(k) if k else None for k in node.keys]
        values = [ast_eval_node(v) for v in node.values]
        return dict(zip(keys, values))
    elif isinstance(node, ast.BinOp):
        # 处理二元运算：加减乘除等
        left = ast_eval_node(node.left)
        right = ast_eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            return left / right
        elif isinstance(node.op, ast.FloorDiv):
            return left // right
        elif isinstance(node.op, ast.Mod):
            return left % right
        elif isinstance(node.op, ast.Pow):
            return left ** right
    elif isinstance(node, ast.UnaryOp):
        # 处理一元运算：负号等
        operand = ast_eval_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        elif isinstance(node.op, ast.USub):
            return -operand
    elif isinstance(node, ast.Call):
        # 处理函数调用
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name == 'dict':
                # dict() 调用
                result_dict = {}
                for keyword in node.keywords:
                    result_dict[keyword.arg] = ast_eval_node(keyword.value)
                return result_dict
            elif func_name == 'list':
                # list() 调用
                if node.args:
                    return list(ast_eval_node(node.args[0]))
                return []
            elif func_name == 'range':
                # range() 调用
                args = [ast_eval_node(arg) for arg in node.args]
                return list(range(*args))
            elif func_name == 'max':
                # max() 调用
                args = [ast_eval_node(arg) for arg in node.args]
                return max(args)
            elif func_name == 'min':
                # min() 调用
                args = [ast_eval_node(arg) for arg in node.args]
                return min(args)
    elif isinstance(node, ast.Tuple):
        return tuple(ast_eval_node(elem) for elem in node.elts)
    elif isinstance(node, ast.NameConstant):  # True, False, None
        return node.value
    elif isinstance(node, ast.Name):
        # 对于变量引用，返回变量名字符串（简化处理）
        return f"<variable:{node.id}>"

    # 对于其他复杂表达式，尝试字面量解析
    try:
        return ast.literal_eval(node)
    except:
        return f"<unparseable>"


def extract_variables_from_py(content: str, key_map: dict):
    """
    提取指定 keys 的顶层变量赋值，支持复杂的 Python 表达式
    key_map: {目标字段: 源文件变量名}
    """
    result = {}

    try:
        tree = ast.parse(content)
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                var_name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
                for target_key, source_var in key_map.items():
                    if var_name == source_var:
                        try:
                            value = ast_eval_node(node.value)
                            result[target_key] = value
                        except Exception as e:
                            # 如果解析失败，记录错误但继续
                            result[target_key] = f"<parse_error: {e}>"
    except Exception as e:
        return None, f"AST解析失败: {e}"

    # 没有的字段补 None
    for k in key_map:
        if k not in result:
            result[k] = None

    return result, None
