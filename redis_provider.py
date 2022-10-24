import json

from config import Cfg
import redis
from near_multinode_rpc_provider import MultiNodeJsonProviderError,  MultiNodeJsonProvider

pool = redis.ConnectionPool(host=Cfg.REDIS["REDIS_HOST"], port=int(Cfg.REDIS["REDIS_PORT"]), decode_responses=True)

def list_pools_by_id_list(network_id: str, id_list: list) ->list:
    import json
    pool_list = []
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], id_list)
    r.close()
    try:
        pool_list = [json.loads(x) for x in ret if x is not None]
    except Exception as e:
        print(e)
    return pool_list

def list_pools_by_tokens(network_id: str, token1: str, token2: str) ->list:
    import json
    list_pools = []
    id_list = []
    id_list.append(token1)
    id_list.append(token2)
    sorted_tp = sorted(id_list)
    key = "{%s}-{%s}" % (sorted_tp[0], sorted_tp[1])
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_POOL_BY_TOKEN_KEY"], key)
    r.close()
    try:
        list_pools = json.loads(ret)
    except Exception as e:
        print(e)
    return list_pools

def list_farms(network_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_KEY"])
    r.close()
    list_farms = [json.loads(x) for x in ret.values()]
    print(len(list_farms))
    return list_farms


def list_pools(network_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"])
    r.close()
    pools = []
    for id, value in ret.items():
        single_pool = json.loads(value)
        single_pool["id"] = id
        pools.append(single_pool)
    return pools

def get_pool(network_id, pool_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], pool_id)
    r.close()
    single_pool = {}
    if ret:
        single_pool = json.loads(ret)
        single_pool["id"] = pool_id
    return single_pool

def list_top_pools(network_id):
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOP_POOL_KEY"])
    r.close()
    pools = []
    for key, value in ret.items():
        pools.append(json.loads(value))
    return pools

def list_token_price(network_id):
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"])
    r.close()
    return ret

def list_token_price_by_id_list(network_id: str, id_list: list) ->list:
    import json
    token_list = []
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], id_list)
    r.close()
    try:
        token_list = [json.loads(x) if x is not None else None for x in ret]
    except Exception as e:
        print(e)
    return token_list

def get_token_price(network_id, token_contract_id):
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], token_contract_id)
    r.close()
    return ret

def get_proposal_hash_by_id(network_id, proposal_id):
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_PROPOSAL_ID_HASH_KEY"], proposal_id)
    r.close()
    return ret

def list_history_token_price(network_id: str, id_list: list) ->list:
    import json
    token_list = []
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_HISTORY_TOKEN_PRICE_KEY"], id_list)
    r.close()
    try:
        token_list = [json.loads(x) if x is not None else None for x in ret]
    except Exception as e:
        print(e)
    return token_list


def get_token_price_report(network_id: str, token: str):
    import json
    token_report = []
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_REPORT_KEY"], token)
    r.close()
    try:
        token_report = json.loads(ret)
    except Exception as e:
        print(e)
    return token_report


def list_token_metadata(network_id):
    '''
    return:
    {
        'nusdc.ft-fin.testnet': {
            'spec': 'ft-1.0.0', 
            'name': 'NEAR Wrapped USDC', 
            'symbol': 'nUSDC', 
            'icon': 'https://s2.coinmarketcap.com/static/img/coins/64x64/3408.png', 
            'reference': None, 
            'reference_hash': None, 
            'decimals': 2
        },
        ...
    }
    
    '''
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_TOKEN_METADATA_KEY"])
    r.close()
    metadata_obj = {}
    for key, value in ret.items():
        metadata_obj[key] = json.loads(value)
    return metadata_obj


def get_proposal_hash_by_id(network_id: str, id_list: list) -> list:
    proposal_list = []
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hmget(Cfg.NETWORK[network_id]["REDIS_PROPOSAL_ID_HASH_KEY"], id_list)
    r.close()
    try:
        proposal_list = [json.loads(x) if x is not None else None for x in ret]
    except Exception as e:
        print(e)
    return proposal_list


def list_whitelist(network_id):
    '''
    return:
    {
        'nusdc.ft-fin.testnet': {
            'spec': 'ft-1.0.0', 
            'name': 'NEAR Wrapped USDC', 
            'symbol': 'nUSDC', 
            'icon': 'https://s2.coinmarketcap.com/static/img/coins/64x64/3408.png', 
            'reference': None, 
            'reference_hash': None, 
            'decimals': 2
        },
        ...
    }
    
    '''
    import json
    r=redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_WHITELIST_KEY"])
    r.close()
    whitelist_obj = {}
    for key, value in ret.items():
        whitelist_obj[key] = json.loads(value)
    return whitelist_obj


def get_whitelisted_tokens(network_id, token_contract_id):
    redis_key = Cfg.NETWORK[network_id]["REDIS_WHITELISTED_TOKENS_KEY"] + "_" + token_contract_id
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.get(redis_key)
    if ret is None:
        try:
            rpc_conn = MultiNodeJsonProvider(network_id)
            rpc_ret = rpc_conn.view_call(token_contract_id, "get_whitelisted_tokens", b'')
            json_str = "".join([chr(x) for x in rpc_ret["result"]])
            r.setex(redis_key, 600, json_str)
            r.close()
            ret = json.loads(json_str)
        except MultiNodeJsonProviderError as e:
            r.close()
            print("RPC Error: ", e)
    return ret


def get_24h_pool_volume(network_id, pool_id):
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hget(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"], pool_id)
    r.close()
    return json.loads(ret)


def get_dcl_pools_volume_list(network_id, redis_key):

    import json
    r = redis.StrictRedis(connection_pool=pool)
    ret = r.hgetall(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_LIST_KEY"] + "_" + redis_key)
    r.close()
    dcl_pools_volume_list = [json.loads(x) for x in ret.values()]
    return dcl_pools_volume_list


class RedisProvider(object):

    def __init__(self):
        self.r=redis.StrictRedis(connection_pool=pool)
        self.pipe = None
    
    def begin_pipe(self) -> bool:
        if self.pipe is None:
            self.pipe = self.r.pipeline(transaction=True)
            self.farmids = set()
            return True
        else:
            return False
    
    def end_pipe(self) -> bool:
        if self.pipe is not None:
            self.pipe.execute()
            self.pipe = None
            return True
        else:
            return False
    
    # remove farms that not existed in contract
    def review_farmid(self, network_id):
        old = set(self.r.hkeys(Cfg.NETWORK[network_id]["REDIS_KEY"]))
        expired = list(old - self.farmids)
        self.r.hdel(Cfg.NETWORK[network_id]["REDIS_KEY"], *expired)
        return expired


    def add_farm(self, network_id, farm_id, farm_str):
        self.farmids.add(farm_id)
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_KEY"], farm_id, farm_str)
    
    def add_whitelist(self, network_id, whitelist_id, whitelist_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_WHITELIST_KEY"], whitelist_id, whitelist_str)
    
    def add_pool(self, network_id, pool_id, pool_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_POOL_KEY"], pool_id, pool_str)
    
    def add_top_pool(self, network_id, pool_id, pool_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOP_POOL_KEY"], pool_id, pool_str)
    
    def add_token_price(self, network_id, contract_id, price_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_KEY"], contract_id, price_str)

    def add_history_token_price(self, network_id, contract_id, price_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_HISTORY_TOKEN_PRICE_KEY"], contract_id, price_str)

    def add_token_price_report(self, network_id, contract_id, price_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_PRICE_REPORT_KEY"], contract_id, price_str)

    def add_token_metadata(self, network_id, contract_id, metadata_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_TOKEN_METADATA_KEY"], contract_id, metadata_str)
    
    def add_pools_by_tokens(self, network_id, tokens_str, pool_list_str):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_POOL_BY_TOKEN_KEY"], tokens_str, pool_list_str)

    def list_farms(self, network_id):
        return self.r.hgetall(Cfg.NETWORK[network_id]["REDIS_KEY"])

    def add_proposal_id_hash(self, network_id, proposal_id, proposal_hash):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_PROPOSAL_ID_HASH_KEY"], proposal_id, proposal_hash)

    def add_twenty_four_hour_pools_data(self, network_id, pool_id, volume):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_24H_KEY"], pool_id, volume)

    def add_dcl_pools_data(self, network_id, pool_id, volume, redis_key):
        self.r.hset(Cfg.NETWORK[network_id]["REDIS_DCL_POOLS_VOLUME_LIST_KEY"] + "_" + redis_key, pool_id, volume)

    def close(self):
        self.r.close()


if __name__ == '__main__':
    conn = RedisProvider()
    # conn.begin_pipe()
    # conn.add_farm("farm_id_1", "farm_value_1")
    # conn.add_farm("farm_id_2", "farm_value_2")
    # conn.add_farm("farm_id_3", "farm_value_3")
    # conn.end_pipe()
    # p = list_farms("TESTNET")
    # print(p)
    # list_pools("MAINNET")
    # print(list_token_price("MAINNET"))
    # print(list_token_metadata("TESTNET"))
    # a = get_pool("TESTNET", "0")
    # print(a)
    # b = get_pool("TESTNET", "1000")
    # print(b)

    a = list_pools_by_id_list("DEVNET", ['79',])
    print(a)
    # print(get_token_price("MAINNET", "token.v2.ref-finance.near"))



    # r=redis.StrictRedis(connection_pool=pool)
    # r.hset(KEY, "aaa", "AAA")
    # r.hset(KEY, "bbb", "BBB")
    # r.close()

