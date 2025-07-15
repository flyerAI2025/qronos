import ast
import json
from enum import Enum
from pathlib import Path

import pandas as pd

from utils.log_kit import get_logger

logger = get_logger()


def process_framework_account_statistics(framework_status):
    """
    处理单个框架的账户统计信息
    
    从指定框架中提取所有账户的详细统计信息，包括资金曲线、持仓数据等。
    
    Args:
        framework_status: 框架状态对象，包含框架ID、路径等信息
        
    Returns:
        list: 该框架下所有账户的统计信息列表
    """
    logger.info(f"处理框架账户统计: {framework_status.framework_name} ({framework_status.framework_id})")
    
    result = []
    
    if not framework_status.path:
        logger.error(f"框架未下载完成: {framework_status.framework_id}")
        return result

    account_path = Path(framework_status.path) / 'accounts'
    if not account_path.exists():
        logger.warning(f"账户目录不存在: {account_path}")
        return result

    data_path = Path(framework_status.path) / 'data'
    if not data_path.exists():
        logger.warning(f"数据目录不存在: {data_path}")
        return result

    # 获取所有有效的账户配置文件
    account_list = [
        file.stem
        for file in account_path.iterdir()
        if file.is_file() and file.suffix == ".json" and not file.name.startswith('_')
    ]
    
    logger.info(f"框架 {framework_status.framework_name} 中找到 {len(account_list)} 个账户")

    for account_name in account_list:
        try:
            # 读取账户配置
            account_json_path = account_path / f"{account_name}.json"
            account_json = json.loads(account_json_path.read_text(encoding='utf-8'))
            
            # 基础账户信息
            account_info = {
                'edit_id': framework_status.id,
                'framework_id': framework_status.framework_id,
                'framework_name': framework_status.framework_name,
                'account_name': account_name,
                'hour_offset': account_json['account_config']['hour_offset'],
                'strategy_name': account_json['strategy_name'],
                'strategy_config': account_json['strategy_config'],
                'strategy_pool': account_json['strategy_pool'],
            }
            
            # 检查账户信息目录
            account_info_path = data_path / account_name / '账户信息'
            if not account_info_path.exists():
                logger.warning(f'{account_name} 没有生成 [账户信息] 目录，该账户当前下单过····')
                continue
            
            # 处理资金曲线数据
            equity_start_time = None
            equity_path = account_info_path / 'equity.pkl'
            if equity_path.exists():
                try:
                    df: pd.DataFrame = pd.read_pickle(equity_path)
                    equity_start_time = df['time'].min()
                    
                    # 计算24小时数据
                    last_24h_df = df[df['time'] > df['time'] - pd.Timedelta(hours=24)]
                    if not last_24h_df.empty:
                        account_info['eq_pct_24h'] = round(100 * (last_24h_df.iloc[-1]['账户总净值'] / last_24h_df.iloc[0]['账户总净值'] - 1), 2)
                        account_info['eq_pnl_24h'] = round(last_24h_df.iloc[-1]['账户总净值'] - last_24h_df.iloc[0]['账户总净值'], 2)
                        account_info['eq_max_24h'] = last_24h_df['账户总净值'].max()
                        account_info['eq_min_24h'] = last_24h_df['账户总净值'].min()

                    # 格式化资金曲线数据
                    df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    df.rename(columns={
                        '账户总净值': 'equity_amount',
                        '多头选币': 'long_coin_num', '空头选币': 'short_coin_num',
                        '多头仓位': 'long_pos_val', '空头仓位': 'short_pos_val',
                    }, inplace=True)
                    
                    cols = ['equity_amount', 'long_pos_val', 'short_pos_val', 'long_coin_num', 'short_coin_num', 'net',
                            'max2here', 'dd2here', 'long_ratio', 'short_ratio', 'empty_ratio']
                    for col in cols:
                        if col in df.columns:
                            df[col] = df[col].round(2)
                    
                    df_dict = df[['time', *[col for col in cols if col in df.columns]]].to_dict('list')
                    account_info['equity'] = df_dict
                    
                except Exception as e:
                    logger.error(f"处理 {account_name} 资金曲线数据失败: {e}")
            
            # 处理子策略资金曲线
            sub_stg_eqs_path = account_info_path / 'sub_stg_eqs.pkl'
            if sub_stg_eqs_path.exists() and equity_start_time:
                try:
                    account_info['sub_stg_eqs'] = {}
                    sub_stg_eqs_dict = pd.read_pickle(sub_stg_eqs_path)
                    for stg_name, df in sub_stg_eqs_dict.items():
                        # 使用布尔索引过滤数据
                        mask = df['candle_begin_time'] >= equity_start_time
                        if mask.any():
                            # 使用 .loc 直接对过滤后的数据进行操作，避免 SettingWithCopyWarning
                            df.loc[mask, 'candle_begin_time'] = df.loc[mask, 'candle_begin_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
                            df.loc[mask, 'net'] = (100 * (df.loc[mask, 'equity'] / df.loc[mask, 'equity'].iloc[0] - 1)).round(2)
                            account_info['sub_stg_eqs'][stg_name] = df.loc[mask, ['candle_begin_time', 'net']].to_dict('list')
                except Exception as e:
                    logger.error(f"处理 {account_name} 子策略资金曲线失败: {e}")
            
            # 处理现货持仓数据
            pos_spot_path = account_info_path / 'pos_spot.pkl'
            if pos_spot_path.exists():
                try:
                    pos_spot = pd.read_pickle(pos_spot_path)
                    if pos_spot:
                        pos_spot_list = {}
                        for timestamp_key, df in pos_spot.items():
                            if not df.empty:
                                pos_spot_list[timestamp_key] = df.reset_index().to_dict('records')
                        account_info['pos_spot'] = pos_spot_list
                except Exception as e:
                    logger.error(f"处理 {account_name} 现货持仓数据失败: {e}")
            
            # 处理合约持仓数据
            pos_swap_path = account_info_path / 'pos_swap.pkl'
            if pos_swap_path.exists():
                try:
                    pos_swap = pd.read_pickle(pos_swap_path)
                    if pos_swap:
                        pos_swap_list = {}
                        for timestamp_key, df in pos_swap.items():
                            if not df.empty:
                                pos_swap_list[timestamp_key] = df.reset_index().to_dict('records')
                        account_info['pos_swap'] = pos_swap_list
                except Exception as e:
                    logger.error(f"处理 {account_name} 合约持仓数据失败: {e}")

            result.append(account_info)
            logger.debug(f"成功处理账户: {account_name}")
            
        except Exception as e:
            logger.error(f"处理账户 {account_name} 统计信息失败: {e}")
            continue
    
    logger.info(f"框架 {framework_status.framework_name} 处理完成，成功处理 {len(result)} 个账户")
    return result


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
    
    根据 is_lock 状态管理文件名前缀：
    - is_lock=True: 生成 _用户名.py 文件（锁定账号），删除 用户名.py 文件
    - is_lock=False: 生成 用户名.py 文件（正常使用），删除 _用户名.py 文件

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

    # 根据 is_lock 状态确定文件名
    is_lock = account_json.get('is_lock', False)
    if is_lock:
        # 锁定状态：生成 _用户名.py 文件
        target_py_path = accounts_dir / f'_{account_name}.py'
        old_py_path = accounts_dir / f'{account_name}.py'
    else:
        # 正常状态：生成 用户名.py 文件
        target_py_path = accounts_dir / f'{account_name}.py'
        old_py_path = accounts_dir / f'_{account_name}.py'

    # 删除旧的文件（如果存在）
    if old_py_path.exists():
        old_py_path.unlink(missing_ok=True)
        logger.info(f"已删除旧文件: {old_py_path}")

    # 如果是更新模式，先读取现有文件（从目标文件路径读取）
    existing_data = {}
    if update_mode:
        existing_data = read_existing_py_file(target_py_path)

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
    target_py_path.write_text(py_content, encoding='utf-8')
    logger.info(f"已生成账户配置文件: {target_py_path}")
    return target_py_path


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


def ast_eval_node_with_context(node, var_context=None):
    """
    递归解析 AST 节点，支持变量上下文
    
    Args:
        node: AST 节点
        var_context: 变量上下文字典，用于替换变量引用
    
    Returns:
        解析后的值
    """
    if var_context is None:
        var_context = {}
        
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Str):  # Python < 3.8 兼容
        return node.s
    elif isinstance(node, ast.Num):  # Python < 3.8 兼容
        return node.n
    elif isinstance(node, ast.List):
        return [ast_eval_node_with_context(elem, var_context) for elem in node.elts]
    elif isinstance(node, ast.Dict):
        keys = [ast_eval_node_with_context(k, var_context) if k else None for k in node.keys]
        values = [ast_eval_node_with_context(v, var_context) for v in node.values]
        return dict(zip(keys, values))
    elif isinstance(node, ast.BinOp):
        # 处理二元运算：加减乘除等
        left = ast_eval_node_with_context(node.left, var_context)
        right = ast_eval_node_with_context(node.right, var_context)
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
        operand = ast_eval_node_with_context(node.operand, var_context)
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
                    result_dict[keyword.arg] = ast_eval_node_with_context(keyword.value, var_context)
                return result_dict
            elif func_name == 'list':
                # list() 调用
                if node.args:
                    return list(ast_eval_node_with_context(node.args[0], var_context))
                return []
            elif func_name == 'range':
                # range() 调用
                args = [ast_eval_node_with_context(arg, var_context) for arg in node.args]
                return list(range(*args))
            elif func_name == 'max':
                # max() 调用
                args = [ast_eval_node_with_context(arg, var_context) for arg in node.args]
                return max(args)
            elif func_name == 'min':
                # min() 调用
                args = [ast_eval_node_with_context(arg, var_context) for arg in node.args]
                return min(args)
    elif isinstance(node, ast.Tuple):
        return tuple(ast_eval_node_with_context(elem, var_context) for elem in node.elts)
    elif isinstance(node, ast.NameConstant):  # True, False, None
        return node.value
    elif isinstance(node, ast.Name):
        # 优先使用上下文中的变量值
        if node.id in var_context:
            return var_context[node.id]
        # 对于未知变量引用，返回变量名字符串
        return f"<variable:{node.id}>"

    # 对于其他复杂表达式，尝试字面量解析
    try:
        return ast.literal_eval(node)
    except:
        # 如果还是无法解析，尝试执行代码（安全模式）
        try:
            # 对于复杂表达式，尝试编译并执行
            # 这是一个安全的方式，因为我们只处理配置文件
            code = compile(ast.Expression(node), '<string>', 'eval')
            
            # 创建一个安全的执行环境，包含变量上下文
            safe_dict = {
                'dict': dict,
                'list': list,
                'tuple': tuple,
                'set': set,
                'range': range,
                'max': max,
                'min': min,
                'len': len,
                'sum': sum,
                'abs': abs,
                'round': round,
                'True': True,
                'False': False,
                'None': None,
            }
            # 添加变量上下文
            safe_dict.update(var_context)
            
            result = eval(code, {"__builtins__": {}}, safe_dict)
            return result
        except Exception:
            return f"<unparseable>"


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
    elif isinstance(node, ast.ListComp):
        # 处理列表推导式 [expr for target in iter if condition]
        # 支持多个生成器：[expr for x in iter1 for y in iter2 ...]
        try:
            # 处理多个生成器的情况
            generators = node.generators
            if not generators:
                return f"<list_comprehension>"
            
            # 递归处理所有生成器，构建嵌套循环
            def process_generators(gen_index, current_context):
                if gen_index >= len(generators):
                    # 所有生成器都处理完了，计算元素表达式
                    return [ast_eval_node_with_context(node.elt, current_context)]
                
                # 处理当前生成器
                generator = generators[gen_index]
                iter_node = generator.iter
                target_var = generator.target
                
                # 获取迭代器的值
                iter_values = ast_eval_node_with_context(iter_node, current_context)
                
                if not isinstance(target_var, ast.Name) or not isinstance(iter_values, list):
                    return [f"<complex_generator_{gen_index}>"]
                
                target_var_name = target_var.id
                result = []
                
                # 对每个值进行迭代
                for value in iter_values:
                    # 创建新的上下文，包含当前变量
                    new_context = current_context.copy()
                    new_context[target_var_name] = value
                    
                    # 递归处理下一个生成器
                    sub_results = process_generators(gen_index + 1, new_context)
                    result.extend(sub_results)
                
                return result
            
            # 从第一个生成器开始处理
            result = process_generators(0, {})
            return result
            
        except Exception as e:
            logger.warning(f"列表推导式解析失败: {e}")
            return f"<list_comprehension>"
    elif isinstance(node, ast.SetComp):
        # 处理集合推导式
        return f"<set_comprehension>"
    elif isinstance(node, ast.DictComp):
        # 处理字典推导式
        return f"<dict_comprehension>"
    elif isinstance(node, ast.GeneratorExp):
        # 处理生成器表达式
        return f"<generator_expression>"

    # 对于其他复杂表达式，尝试字面量解析
    try:
        return ast.literal_eval(node)
    except:
        # 如果还是无法解析，尝试执行代码（安全模式）
        try:
            # 对于复杂表达式，尝试编译并执行
            # 这是一个安全的方式，因为我们只处理配置文件
            code = compile(ast.Expression(node), '<string>', 'eval')
            
            # 创建一个安全的执行环境
            safe_dict = {
                'dict': dict,
                'list': list,
                'tuple': tuple,
                'set': set,
                'range': range,
                'max': max,
                'min': min,
                'len': len,
                'sum': sum,
                'abs': abs,
                'round': round,
                'True': True,
                'False': False,
                'None': None,
            }
            
            result = eval(code, {"__builtins__": {}}, safe_dict)
            return result
        except Exception:
            return f"<unparseable>"


def extract_variables_from_py(content: str, key_map: dict):
    """
    提取指定 keys 的顶层变量赋值，支持复杂的 Python 表达式
    key_map: {目标字段: 源文件变量名}
    """
    result = {}

    try:
        # 方法1：尝试直接执行代码在安全环境中
        try:
            # 创建一个安全的执行环境
            safe_globals = {
                "__builtins__": {},
                'dict': dict,
                'list': list,
                'tuple': tuple,
                'set': set,
                'range': range,
                'max': max,
                'min': min,
                'len': len,
                'sum': sum,
                'abs': abs,
                'round': round,
                'True': True,
                'False': False,
                'None': None,
                # 添加一些配置文件中可能用到的模块和函数
                'os': type('MockOS', (), {
                    'cpu_count': lambda: 8,  # 模拟 os.cpu_count()
                })(),
                'Path': type('MockPath', (), {
                    '__call__': lambda self, *args: type('MockPathInstance', (), {
                        '__truediv__': lambda self, other: self,
                        'exists': lambda: False,
                    })()
                })(),
            }
            safe_locals = {}
            
            # 执行整个代码，提取需要的变量
            exec(content, safe_globals, safe_locals)
            
            # 从执行结果中提取需要的变量
            for target_key, source_var in key_map.items():
                if source_var in safe_locals:
                    result[target_key] = safe_locals[source_var]
                else:
                    result[target_key] = None
            
            logger.info("使用 exec 方法成功解析配置文件")
            return result, None
            
        except Exception as exec_error:
            logger.warning(f"exec 方法解析失败: {exec_error}，回退到 AST 方法")
            
        # 方法2：回退到 AST 解析方法
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
                            logger.error(f"AST 解析变量 {source_var} 失败: {e}")
                            result[target_key] = f"<parse_error: {e}>"
                                
    except Exception as e:
        return None, f"代码解析失败: {e}"

    # 没有的字段补 None
    for k in key_map:
        if k not in result:
            result[k] = None

    return result, None
