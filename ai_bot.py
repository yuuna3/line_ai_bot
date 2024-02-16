import os
import sys
import requests

from flask import Flask, request, abort

from linebot.v3 import WebhookHandler

from linebot.v3.webhooks import MessageEvent, TextMessageContent, UserSource
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.exceptions import InvalidSignatureError

from openai import AzureOpenAI

# get LINE credentials from environment variables
channel_access_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
channel_secret = os.environ["LINE_CHANNEL_SECRET"]

if channel_access_token is None or channel_secret is None:
    print("Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variable.")
    sys.exit(1)

# get Azure OpenAI credentials from environment variables
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_key = os.getenv("AZURE_OPENAI_KEY")

if azure_openai_endpoint is None or azure_openai_key is None:
    raise Exception(
        "Please set the environment variables AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY to your Azure OpenAI endpoint and API key."
    )

print(os.getenv("OPENWEATHERMAP_API_KEY"))

openweathermap_api_key = os.getenv("OPENWEATHERMAP_API_KEY")

if openweathermap_api_key is None:
    raise Exception(
        "Please set the environment variable OPENWEATHERMAP_API_KEY to your OpenWeatherMap API key."
    )

app = Flask(__name__)

handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)

ai_model = "mulabo_gpt35"
ai = AzureOpenAI(azure_endpoint=azure_openai_endpoint, api_key=azure_openai_key, api_version="2023-05-15")

system_role = """
あなたはめちゃくちゃ元気な近所のお兄ちゃんです。話し方はとてもラフで、こてこての方言で話します。大学に通っていて、宇宙について研究していて、よく宇宙について妄想を繰り広げます。また、邦ロックとクラシックが好きで、チャット中3回に1回の頻度で解説とともに曲をお勧めします。
"""
conversation = None


def init_conversation(sender):
    conv = [{"role": "system", "content": system_role}]
    conv.append({"role": "user", "content": f"私の名前は{sender}です。"})
    conv.append({"role": "assistant", "content": "分かりました。"})
    return conv
def get_ai_response(sender, text):
    global conversation
    if conversation is None:
        conversation = init_conversation(sender)

    if text in ["リセット", "clear", "reset", "キャンセル"]:
        conversation = init_conversation(sender)
        response_text = "会話をリセットしました。"

    else:
        conversation.append({"role": "user", "content": text})
        response = ai.chat.completions.create(model=ai_model, messages=conversation)
        response_text = response.choices[0].message.content
        conversation.append({"role": "assistant", "content": response_text})
    return response_text


@app.route("/callback", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        abort(400, e)

    return "OK"


def get_weather():
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": 34.7123,
        "lon": 135.2396,
        "appid": openweathermap_api_key,
        "units": "metric"
    }
    response = requests.get(url, params=params)
    data = response.json()

    weather_description = data["weather"][0]["description"]
    temp = data["main"]["temp"]
    return f"現在の天気は{weather_description}で、気温は{temp}度やで。"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if isinstance(event.source, UserSource):
            profile = line_bot_api.get_profile(event.source.user_id)

            if text == "天気":
                weather_info = get_weather()
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=weather_info)],
                    )
                )

            else:
                 response = get_ai_response(profile.display_name, text)
                 line_bot_api.reply_message_with_http_info(
                     ReplyMessageRequest(
                         reply_token=event.reply_token,
                         messages=[TextMessage(text=response)],
                     )
                 )

        else:
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="Received message: " + text)],
                )
            )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
