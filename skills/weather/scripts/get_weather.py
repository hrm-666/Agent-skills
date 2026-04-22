import argparse
from uapi import UapiClient
from uapi.errors import UapiError

client = UapiClient("https://uapis.cn")


def main() -> None:
    parser = argparse.ArgumentParser(description="天气查询工具")
    parser.add_argument("--city",required=True,help="待查询的城市")
    args = parser.parse_args()

    print(args.city)

    try:
        response = client.misc.get_misc_weather(city=args.city,
                                              extended=True,
                                              lang="zh")
        result = {
            "city": args.city,
            "weather": response["weather"],
            "temperature": response["temperature"],
            "humidity": response["humidity"],
            "aqi": response["aqi"],
            "aqi_category": response["aqi_category"],
        }
        print(result)
    except UapiError as exc:
        print(f"The weather query service is temporarily unavailable. API error: {exc}")

if __name__ == "__main__":
    main()