# lambda/index.py
import json
import os
# import boto3
# import re  # 正規表現モジュールをインポート
# from botocore.exceptions import ClientError

import urllib.request
import urllib.error

FASTAPI_ENDPOINT_URL = 'https://54f1-34-16-128-67.ngrok-free.app/generate'

# # Lambda コンテキストからリージョンを抽出する関数
# def extract_region_from_arn(arn):
#     # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
#     match = re.search('arn:aws:lambda:([^:]+):', arn)
#     if match:
#         return match.group(1)
#     return "us-east-1"  # デフォルト値

# # グローバル変数としてクライアントを初期化（初期値）
# bedrock_client = None

# # モデルID
# MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")

def lambda_handler(event, context):
    try:
        # # コンテキストから実行リージョンを取得し、クライアントを初期化
        # global bedrock_client
        # if bedrock_client is None:
        #     region = extract_region_from_arn(context.invoked_function_arn)
        #     bedrock_client = boto3.client('bedrock-runtime', region_name=region)
        #     print(f"Initialized Bedrock client in region: {region}")
        
        print("Received event:", json.dumps(event))
        
        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")
        
        # リクエストボディの解析
        body = json.loads(event['body'])
        message = body['message']
        conversation_history = body.get('conversationHistory', [])
        
        print("Processing message:", message)
        # print("Using model:", MODEL_ID)
        
        # 会話履歴を使用
        messages = conversation_history.copy()
        
        # ユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": message
        })

        # --- FastAPI呼び出し処理 ---
        assistant_response = ''
        try:
            if not FASTAPI_ENDPOINT_URL:
                raise ValueError('FastAPI endpoint URL is not configured correctly.')
            
            # 1. APIに送るデータを作成（FastAPIのSimpleGenerateRequestに合わせる）
            request_data_dict = {'prompt': message}
            request_data_bytes = json.dumps(request_data_dict).encode('utf-8')

            # 2. リクエストオブジェクトを作成
            req = urllib.request.Request(
                FASTAPI_ENDPOINT_URL,
                data=request_data_bytes,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            print(f'Calling FastAPI endpoint: {FASTAPI_ENDPOINT_URL} with prompt: {message[:100]}...')

            # 3. APIを呼び出し，レスポンスを取得（タイムアウトを設定）
            with urllib.request.urlopen(req, timeout=300) as response:
                response_status = response.getcode()
                print(f'FastAPI response status: {response_status}')
                if 200 <= response_status < 300:
                    # 4. レスポンスボディを読み取り，JSONとしてパース
                    response_body_bytes = response.read()
                    response_body_str = response_body_bytes.decode('utf-8')
                    print(f'FastAPI response body: {response_body_str}')
                    api_response = json.loads(response_body_str)

                    # 5. APIからの応答を取得（FastAPIのGenerationResponseの'generated_text'キー
                    assistant_response = api_response.get('generated_text')
                    if not assistant_response:
                         print("Warning: 'generated_text' not found in FastAPI response.")
                         assistant_response = "Error: Could not parse response from custom model API."
                    else:
                        error_message = f"Error: Custom model API returned status code {response_status}."
                    
                        try:
                            # エラーレスポンスの内容も表示試行
                            error_body = response.read().decode('utf-8')
                            error_message += f" Body: {error_body}"
                        except Exception:
                            pass # エラーボディ読み取り失敗は無視
                        print(error_message)
                        assistant_response = error_message
        
        except urllib.error.HTTPError as e:
            # HTTPエラー (4xx, 5xx など)
            error_body_str = "N/A"
            try:
                error_body_str = e.read().decode('utf-8')
            except Exception:
                pass
            print(f"FastAPI call failed with HTTPError: {e.code} {e.reason}. Response body: {error_body_str}")
            assistant_response = f"Error: Failed to get response from custom model API ({e.code} {e.reason})."
        except urllib.error.URLError as e:
            # URL関連のエラー (接続失敗、タイムアウトなど)
            print(f"FastAPI call failed with URLError: {e.reason}")
            assistant_response = f"Error: Could not connect to the custom model API. ({e.reason})"
        except json.JSONDecodeError as e:
            print(f"Failed to parse FastAPI response: {e}. Response body was: {response_body_str}")
            assistant_response = "Error: Invalid response format from the custom model API."
        except ValueError as e: # 設定ミス用
             print(f"Configuration error: {e}")
             assistant_response = f"Error: Lambda configuration error - {e}"
        except Exception as e:
            # その他の予期せぬエラー
            import traceback
            print(f"An unexpected error occurred during FastAPI call: {e}")
            print(traceback.format_exc()) # スタックトレースを出力
            assistant_response = "Error: An unexpected error occurred while calling the custom model API."

        # --- FastAPI呼び出し処理 ここまで ---

        
        # # Nova Liteモデル用のリクエストペイロードを構築
        # # 会話履歴を含める
        # bedrock_messages = []
        # for msg in messages:
        #     if msg["role"] == "user":
        #         bedrock_messages.append({
        #             "role": "user",
        #             "content": [{"text": msg["content"]}]
        #         })
        #     elif msg["role"] == "assistant":
        #         bedrock_messages.append({
        #             "role": "assistant", 
        #             "content": [{"text": msg["content"]}]
        #         })
        
        # # invoke_model用のリクエストペイロード
        # request_payload = {
        #     "messages": bedrock_messages,
        #     "inferenceConfig": {
        #         "maxTokens": 512,
        #         "stopSequences": [],
        #         "temperature": 0.7,
        #         "topP": 0.9
        #     }
        # }
        
        # print("Calling Bedrock invoke_model API with payload:", json.dumps(request_payload))
        
        # # invoke_model APIを呼び出し
        # response = bedrock_client.invoke_model(
        #     modelId=MODEL_ID,
        #     body=json.dumps(request_payload),
        #     contentType="application/json"
        # )
        
        # # レスポンスを解析
        # response_body = json.loads(response['body'].read())
        # print("Bedrock response:", json.dumps(response_body, default=str))
        
        # # 応答の検証
        # if not response_body.get('output') or not response_body['output'].get('message') or not response_body['output']['message'].get('content'):
        #     raise Exception("No response content from the model")
        
        # # アシスタントの応答を取得
        # assistant_response = response_body['output']['message']['content'][0]['text']
        
        # アシスタントの応答を会話履歴に追加
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }
        
    except Exception as error:
        print("Error:", str(error))
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }
