import dotenv

from src.tweet import tweet_network_stats

dotenv.load_dotenv()

if __name__ == "__main__":
    tweet_network_stats()
