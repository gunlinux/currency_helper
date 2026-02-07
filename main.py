from dataclasses import dataclass, field
import logging
import os
import sys
import typing
import json

from dotenv import load_dotenv
import requests

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class CurrencyApi:
    api_key: str
    pairs: list[str] = field(default_factory=list)
    default: str = "RUB"
    fallback: dict[str, float] = field(default_factory=dict)
    GET_URL = "https://currate.ru/api/"

    def _get_currency_list(self) -> typing.Any:
        params = {
            "get": "currency_list",
            "key": self.api_key,
        }
        req = requests.get(self.GET_URL, params=params)
        return req.json()

    def get_currency_list(self) -> list[str]:
        r = self._get_currency_list()
        if data := r.get("data"):
            return data
        return []

    def get_pairs(self):
        currency_list = self.get_currency_list()
        out = []
        for pair in self.pairs:
            if pair != self.default:
                if f"{pair}{self.default}" in currency_list:
                    out.append(f"{pair}{self.default}")
                elif f"USD{pair}" in currency_list:
                    out.append(f"USD{pair}")
                elif f"EUR{pair}" in currency_list:
                    out.append(f"EUR{pair}")
                else:
                    logger.warning("Pair not available via direct or USD/EUR: %s", pair)
            else:
                logger.warning("Currency not in list: %s", pair)
        return ",".join(out)

    def _get_api_pairs(self) -> typing.Any:
        params = {
            "get": "rates",
            "pairs": self.get_pairs(),
            "key": self.api_key,
        }
        req = requests.get(self.GET_URL, params=params)
        return req.json()

    def transform(self, pair: str, pairs: dict[str, float]):
        default = self.default

        # via USD
        usd_pair = f"USD{pair}"
        usd_default = f"USD{default}"

        if usd_pair in pairs and usd_default in pairs:
            logger.info("Calculated %s via USD", f"{pair}{default}")
            pairs[f"{pair}{default}"] = pairs[usd_default] / pairs[usd_pair]
            return

        # via EUR
        eur_pair = f"EUR{pair}"
        eur_default = f"EUR{default}"

        if eur_pair in pairs and eur_default in pairs:
            logger.info("Calculated %s via EUR", f"{pair}{default}")
            pairs[f"{pair}{default}"] = pairs[eur_default] / pairs[eur_pair]
            return

    def get_api_pairs(self) -> dict[str, float]:
        pairs = self._get_api_pairs()
        out_pairs = {}
        if data := pairs.get("data"):
            for pair, value in data.items():
                out_pairs[pair] = float(value)
        for fallback_pair, value in self.fallback.items():
            if fallback_pair not in out_pairs:
                out_pairs[fallback_pair] = value

        for pair in self.pairs:
            if f"{pair}{self.default}" not in out_pairs:
                self.transform(pair, out_pairs)
        return out_pairs


def unpack_fallback(fallback: str) -> dict[str, float]:
    d = {}
    for curr in fallback.split(","):
        pair, value = curr.split(":")
        d[pair] = float(value)
    return d


def help() -> None:
    print(f"{sys.argv[0]} [OUTPUT_FILE.json]")


def main() -> None:
    if len(sys.argv) != 2:
        help()
        sys.exit(1)

    api_key = os.getenv("API_KEY")
    donations = os.getenv("DONATIONS", "BYN,EUR,KZT,RUB,UAH,USD,BRL,TRY,PLN")
    donations = donations.split(",")
    fallback = os.getenv("FALLBACK", "BLRRUB:14.00,PLNRUB:21.50")
    fallback = unpack_fallback(fallback)

    if api_key is None:
        raise ValueError()
    logger.info("Hello from currencies!")
    currency_api = CurrencyApi(
        api_key=api_key, pairs=donations, default="RUB", fallback=fallback
    )
    try:
        currencies = currency_api.get_api_pairs()
    except Exception as e:
        logger.critical("currency failed to get: %s", e)
        return

    logger.info("Final currency rates: %s", currencies)
    with open(sys.argv[1], "w") as f:
        json.dump(currencies, f)


if __name__ == "__main__":
    main()
