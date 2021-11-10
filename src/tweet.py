import os
from typing import Dict

import tweepy
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

SUBGRAPH_API_URL = "https://api.thegraph.com/subgraphs/name/data-nexus/rocket-pool-goerli"


def _fetch_stats() -> Dict:
    transport = RequestsHTTPTransport(
        url=SUBGRAPH_API_URL,
        use_json=True,
        headers={
            "Content-type": "application/json",
        },
        retries=3,
    )

    client = Client(transport=transport, fetch_schema_from_transport=True)
    query = gql('''
        query getRocketPoolNetworkStats {}
    ''')

    data = client.execute(query)
    return data


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


def tweet_network_stats() -> None:
    tweepy_api = _auth_tweepy()
    stats = _fetch_stats()
    # TODO: send tweet with stats
