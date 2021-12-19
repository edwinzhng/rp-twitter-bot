import math
import os
import re
import tempfile
from collections import defaultdict
from time import time
from typing import Dict, Optional, Tuple, Union

import dotenv
import plotly.express as px
import requests
import tweepy
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from web3 import Web3

TWEET_MSG = """
🪙 Staking
TVL: Ξ{tvl} ({tvl_change}) - ${tvl_usd}
Staking Pool: Ξ{staker_eth_in_deposit_pool}
rETH Price: Ξ{rETH_price:.4f} ({rETH_apy:.1f}% APY)
Average Commission: {avg_minipool_commission:.2f}%

🖥️ Nodes
Registered Nodes: {node_count}
Staking Minipools: {staking_minipools}
ETH Validator Share: {percent_validators:.2f}%
Commission: {minipool_commission:.2f}%
RPL Price: Ξ{rpl_price:.4f}
RPL Staked: {total_rpl_staked} (Effective {effective_rpl_staked})
"""

BEACONCHAIN_API_URL = "https://beaconcha.in/api/v1/epoch/latest"
BEACONCHAIN_BLOCKS_URL = (
    "https://beaconcha.in/blocks/data?draw=0&"
    "start={start}&length=100&search%5Bvalue%5D=RP-"
)

COINGECKO_API_URL = (
    "https://api.coingecko.com/api/v3/coins/ethereum?"
    "localization=false&tickers=false&market_data=true"
    "&community_data=false&developer_data=false&sparkline=false"
)
SUBGRAPH_BASE_URL = "https://gateway.thegraph.com/api/"
SUBGRAPH_API_URL = "subgraphs/id/0xa508c16666c5b8981fa46eb32784fccc01942a71-3"
STAKER_ETH_PER_MINIPOOL = 16
ETH_PER_MINIPOOL = 32


NUMBER_SYMBOLS = ['', 'k', 'M', 'B', 'T']


dotenv.load_dotenv()


def _pretty_print_num(n) -> str:
    """Convert numbers to a more readable format, eg) 115.5k, 12.3M"""
    n = float(n)
    symbol_idx = max(
        0,
        min(
            len(NUMBER_SYMBOLS) - 1,
            int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))
        )
    )

    value = n / 10**(3 * symbol_idx)
    symbol = NUMBER_SYMBOLS[symbol_idx]
    if n < 1000 and n.is_integer():
        precision = 0
    elif value < 10 or n < 10000:
        precision = 2
    else:
        precision = 1
    return '{:.{precision}f}{}'.format(value, symbol, precision=precision)


def _wei_to_eth(val: Union[str, int]) -> float:
    if type(val) == str:
        val = int(val)
    return float(Web3.fromWei(val, 'ether'))


def _execute_rocketpool_gql(query, variable_values: Optional[Dict] = None) -> Client:
    subgraph_api_key = os.getenv("SUBGRAPH_API_KEY")
    url = SUBGRAPH_BASE_URL + f"{subgraph_api_key}/" + SUBGRAPH_API_URL
    transport = RequestsHTTPTransport(
        url=url,
        use_json=True,
        headers={
            "Content-type": "application/json",
        },
        retries=3,
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)
    data = client.execute(query, variable_values=variable_values)
    return data


def _fetch_rocketpool_stats() -> Tuple[Dict, Dict]:
    query = gql('''
        query protocolMetrics {
            rocketPoolProtocols {
                lastNetworkNodeBalanceCheckPoint {
                    previousCheckpointId
                    stakingMinipools
                    queuedMinipools
                    newMinipoolFee
                    averageFeeForActiveMinipools
                    nodesRegistered
                    rplPriceInETH
                    rplStaked
                    effectiveRPLStaked
                    blockTime
                }
                lastNetworkStakerBalanceCheckPoint {
                    previousCheckpointId
                    stakerETHWaitingInDepositPool
                    rETHExchangeRate
                    blockTime
                }
            }
        }
    ''')
    data = _execute_rocketpool_gql(query)
    data = data["rocketPoolProtocols"][0]
    node_stats = data["lastNetworkNodeBalanceCheckPoint"]
    staker_stats = data["lastNetworkStakerBalanceCheckPoint"]
    return node_stats, staker_stats


def _fetch_network_staker_balance(checkpointId) -> Dict:
    query = gql('''
        query stakerBalance($checkpointId: ID!) {
            networkStakerBalanceCheckpoint(id: $checkpointId) {
                id
                previousCheckpointId
                rETHExchangeRate
                blockTime
            }
        }
    ''')
    data = _execute_rocketpool_gql(query, variable_values={"checkpointId": checkpointId})
    network_staker_stats = data["networkStakerBalanceCheckpoint"]
    return network_staker_stats


def _fetch_tvl_yesterday(stakerCheckpointId, nodeCheckpointId) -> Dict:
    query = gql('''
        query nodeBalance($stakerCheckpointId: ID!, $nodeCheckpointId: ID!) {
            networkStakerBalanceCheckpoint(id: $stakerCheckpointId) {
                stakerETHWaitingInDepositPool
            }
            networkNodeBalanceCheckpoint(id: $nodeCheckpointId) {
                stakingMinipools
                queuedMinipools
                rplPriceInETH
                rplStaked
            }
        }
    ''')
    variables = {"stakerCheckpointId": stakerCheckpointId, "nodeCheckpointId": nodeCheckpointId}
    data = _execute_rocketpool_gql(query, variable_values=variables)
    staker_stats = data["networkStakerBalanceCheckpoint"]
    node_stats = data["networkNodeBalanceCheckpoint"]

    staker_eth_in_deposit_pool = _wei_to_eth(staker_stats["stakerETHWaitingInDepositPool"])
    staking_minipools = int(node_stats["stakingMinipools"])
    queued_minipools = int(node_stats["queuedMinipools"])
    rpl_price = _wei_to_eth(node_stats["rplPriceInETH"])
    total_rpl_staked = _wei_to_eth(node_stats["rplStaked"])
    tvl = (staking_minipools * ETH_PER_MINIPOOL) + \
            (queued_minipools * STAKER_ETH_PER_MINIPOOL) + \
            staker_eth_in_deposit_pool + (total_rpl_staked * rpl_price)
    return tvl


def _fetch_eth_stats() -> Tuple[float, int]:
    # Fetch # of validators from beaconcha.in
    data = requests.get(BEACONCHAIN_API_URL).json()
    active_eth_validators = int(data['data']['validatorscount'])

    # Fetch ETH/USD price from Coingecko
    data = requests.get(COINGECKO_API_URL).json()
    current_price = data['market_data']['current_price']
    eth_price_usd = float(current_price['usd'])
    return eth_price_usd, active_eth_validators


def _auth_tweepy() -> tweepy.API:
    # Fetch credentials
    consumer_key = os.getenv("CONSUMER_KEY")
    consumer_secret = os.getenv("CONSUMER_SECRET")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    # Authenticate
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    return tweepy.API(auth)


def _is_valid_time_since_last_checkpoint(node_stats, staker_stats, max_hours=1) -> bool:
    curr_time = int(time())
    node_ckpt_diff_hours = (curr_time - int(node_stats["blockTime"])) / 3600
    staker_ckpt_diff_hours = (curr_time - int(staker_stats["blockTime"])) / 3600
    print(f"Node checkpoint last updated {node_ckpt_diff_hours:.2f} hours ago")
    print(f"Staker checkpoint last updated {staker_ckpt_diff_hours:.2f} hours ago")

    if node_ckpt_diff_hours < max_hours or staker_ckpt_diff_hours < max_hours:
        return True

    print(f"Time since last checkpoint longer than {max_hours} hour(s), skipping tweet")
    return False


def _compute_rETH_apy(staker_stats):
    # Average APY over num_lookback_days
    num_lookback_days = 3
    prev_staker_stats = staker_stats
    for _ in range(num_lookback_days):
        prev_staker_stats = _fetch_network_staker_balance(prev_staker_stats["previousCheckpointId"])

    # Calculate time period
    block_time_diff = int(staker_stats["blockTime"]) - int(prev_staker_stats["blockTime"])
    seconds_per_year = 365 * 24 * 60 * 60
    compounding_periods = seconds_per_year / block_time_diff

    # Compute current APY
    current_rate = _wei_to_eth(float(staker_stats["rETHExchangeRate"]))
    prev_rate = _wei_to_eth(float(prev_staker_stats["rETHExchangeRate"]))
    rETH_yield = current_rate / prev_rate
    rETH_apy = 100 * ((rETH_yield**compounding_periods) - 1)
    return rETH_apy


def _plot_clients(clients: Dict[str, int]):
    names = ["Lighthouse", "Nimbus", "Prysm", "Teku"]
    values = [clients["L"], clients["N"], clients["P"], clients["T"]]
    colors = ["#CAB8FF", "#FCFFA6", "#C1FFD7", "#B5DEFF"]
    fig = px.pie(
        names=names,
        values=values,
        color_discrete_sequence=colors
    )
    fig['data'][0].update({
        'textinfo': 'label+value+percent',
        'texttemplate': '<b>%{label}</b></br></br>%{value} (%{percent})', 
        'textposition': 'outside',
        'showlegend': False
    })
    fig.update_layout(
        margin=dict(l=10, r=10, t=60, b=10),
        title_text='Rocket Pool Block Proposals',
        title_x=0.5,
        title_font={"size": 28}
    )
    return fig


def _fetch_node_client_diversity():
    print("Fetching client diversity...")
    blocks = []
    blocks_url = BEACONCHAIN_BLOCKS_URL.format(start=0)
    res = requests.get(blocks_url).json()
    records = res["recordsFiltered"]
    blocks.extend(res["data"])

    cur_start = 100
    while len(blocks) < records:
        blocks_url = BEACONCHAIN_BLOCKS_URL.format(start=cur_start)
        res = requests.get(blocks_url).json()
        blocks.extend(res["data"])
        cur_start += 100

    assert len(blocks) == records, f"Only fetched {len(blocks)} RPL blocks of {records}"
    clients = defaultdict(int)
    client_regex = r'q=RP-\w+'
    for block in blocks:
        graffiti = block[-1]
        match = re.search(client_regex, graffiti)
        if match:
            client = match.group(0)[-1]
            clients[client] += 1
    return clients


def tweet_network_stats() -> None:
    node_stats, staker_stats = _fetch_rocketpool_stats()
    should_tweet = _is_valid_time_since_last_checkpoint(node_stats, staker_stats, 1)
    if not should_tweet:
        return

    # ETH stats
    eth_price_usd, active_eth_validators = _fetch_eth_stats()

    # Staking stats
    staker_eth_in_deposit_pool = _wei_to_eth(staker_stats["stakerETHWaitingInDepositPool"])
    rETH_price = _wei_to_eth(staker_stats["rETHExchangeRate"])
    rpl_price = _wei_to_eth(node_stats["rplPriceInETH"])
    total_rpl_staked = _wei_to_eth(node_stats["rplStaked"])
    effective_rpl_staked = _wei_to_eth(node_stats["effectiveRPLStaked"])
    rETH_apy = _compute_rETH_apy(staker_stats)

    # Node stats
    minipool_commission = _wei_to_eth(node_stats["newMinipoolFee"]) * 100
    avg_minipool_commission = _wei_to_eth(node_stats["averageFeeForActiveMinipools"]) * 100
    node_count = int(node_stats["nodesRegistered"])
    staking_minipools = int(node_stats["stakingMinipools"])
    queued_minipools = int(node_stats["queuedMinipools"])
    percent_validators = (staking_minipools / active_eth_validators) * 100

    tvl = (staking_minipools * ETH_PER_MINIPOOL) + \
            (queued_minipools * STAKER_ETH_PER_MINIPOOL) + \
            staker_eth_in_deposit_pool + (total_rpl_staked * rpl_price)
    tvl_usd = tvl * eth_price_usd
    tvl_yesterday = _fetch_tvl_yesterday(
        staker_stats["previousCheckpointId"],
        node_stats["previousCheckpointId"]
    )
    tvl_diff = ((tvl - tvl_yesterday) / tvl_yesterday) * 100
    if tvl_diff >= 0:
        tvl_change = f"📈+{abs(tvl_diff):.1f}%"
    else:
        tvl_change = f"📉-{abs(tvl_diff):.1f}%"

    msg = TWEET_MSG.format(
        tvl=_pretty_print_num(tvl),
        tvl_change=tvl_change,
        tvl_usd=_pretty_print_num(tvl_usd),
        staker_eth_in_deposit_pool=_pretty_print_num(staker_eth_in_deposit_pool),
        minipool_commission=minipool_commission,
        avg_minipool_commission=avg_minipool_commission,
        node_count=_pretty_print_num(node_count),
        staking_minipools=_pretty_print_num(staking_minipools),
        percent_validators=percent_validators,
        rETH_price=rETH_price,
        rETH_apy=rETH_apy,
        rpl_price=rpl_price,
        total_rpl_staked=_pretty_print_num(total_rpl_staked),
        effective_rpl_staked=_pretty_print_num(effective_rpl_staked)
    )

    # Client diversity
    clients = _fetch_node_client_diversity()
    fig = _plot_clients(clients)

    print(f"Sending tweet: {msg}")
    api = _auth_tweepy()
    with tempfile.NamedTemporaryFile() as img_file:
        fig.write_image(img_file.name, format="png", width=960, height=540)
        api.update_status_with_media(status=msg, filename=img_file.name)


if __name__ == "__main__":
    tweet_network_stats()
