import os
import json
import time
from pathlib import Path
import base64
from google import genai
from google.genai import types
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests
from werkzeug.utils import secure_filename
from solders.keypair import Keypair
import io
from PIL import Image


# -----------------------------------------------------------
# Load environment variables
# -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

PUMPPORTAL_API_KEY = os.getenv("PUMPPORTAL_API_KEY")
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")
PORT = int(os.getenv("PORT", 4000))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


print("DEBUG: PUMPPORTAL_API_KEY loaded?", bool(PUMPPORTAL_API_KEY))
print("DEBUG: MORALIS_API_KEY loaded?", bool(MORALIS_API_KEY))

# -----------------------------------------------------------
# Flask app
# -----------------------------------------------------------
app = Flask(
    __name__,
    static_folder="public",
    static_url_path=""
)
app.config["MAX_CONTENT_LENGTH"] = 8 * 500 * 500
CORS(app)


# -----------------------------------------------------------
# Routes
# -----------------------------------------------------------
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/generate-image")
def generate_image():
    if not gemini_client or not GEMINI_API_KEY:
        return jsonify({"error": "Server misconfigured: missing GEMINI_API_KEY"}), 500

    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
        )

        image_bytes = None
        for part in response.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                image_bytes = inline.data
                break

        if not image_bytes:
            return jsonify({"error": "No image data returned from Gemini"}), 500

        # 🔽 NEW: compress + resize before sending to browser
        # 🔽 Compress + force size to 500x500 before sending to browser
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

            # Force exact 500x500, high-quality resize
            target_size = (500, 500)
            img = img.resize(target_size, Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            compressed_bytes = buf.getvalue()
        except Exception:
            # If anything goes wrong, fall back to original bytes
            compressed_bytes = image_bytes


        image_base64 = base64.b64encode(compressed_bytes).decode("utf-8")
        return jsonify({"image_base64": image_base64})

    except Exception as e:
        print("Gemini image error:", e)
        return jsonify({
            "error": "Failed to generate image",
            "details": str(e),
        }), 500



# -----------------------------------------------------------
# Create token(s) via PumpPortal Lightning API
# -----------------------------------------------------------
@app.post("/api/create-token")
def create_token():
    if not PUMPPORTAL_API_KEY:
        return jsonify(
            {"error": "Server misconfigured: missing PUMPPORTAL_API_KEY"}
        ), 500

    # ------------ 1. Read form fields ------------
    amount = request.form.get("amount")  # dev buy amount in SOL (string)
    launch_count_raw = request.form.get("launch_count")
    pool = (request.form.get("pool") or "pump").strip().lower()
    if pool not in ("pump", "bonk"):
        pool = "pump"

    sell_delay_raw = request.form.get("sell_delay")
    ai_image_base64 = request.form.get("ai_image_base64")
    metadata_uri_from_form = request.form.get("metadata_uri")  # from imported token
    instant_sell_flag = request.form.get("instant_sell")       # "on" if checkbox checked

    name = request.form.get("name") or "MyToken"
    symbol = request.form.get("symbol") or "MTK"
    description = request.form.get("description") or ""
    twitter = request.form.get("twitter") or ""
    telegram = request.form.get("telegram") or ""
    website = request.form.get("website") or ""
    image_file = request.files.get("image")

    do_instant_sell = instant_sell_flag == "on"

    if not amount:
        return jsonify({"error": "Amount (SOL) is required"}), 400

    # If we don't have imported metadata, we still require an image file
    if not metadata_uri_from_form and (not image_file or not image_file.filename)and not ai_image_base64:
        return jsonify(
            {"error": "Token image is required (unless importing metadata)"}
        ), 400

    # Parse how many coins to launch
    try:
        launch_count = int(launch_count_raw) if launch_count_raw else 1
    except ValueError:
        launch_count = 1

    if launch_count < 1:
        launch_count = 1
    if launch_count > 10:
        launch_count = 10  # safety cap
    allowed_delays = {1, 2, 5, 10}
    
    try:
        sell_delay_seconds = int(sell_delay_raw) if sell_delay_raw else 5
    except (TypeError, ValueError):
        sell_delay_seconds = 5

    if sell_delay_seconds not in allowed_delays:
        sell_delay_seconds = 5

    # ------------ 2. Determine metadata URI ------------
    if metadata_uri_from_form:
        # Reuse existing metadata (image + socials) from imported token
        metadata_uri = metadata_uri_from_form
    else:
        # Upload metadata + image depending on platform
        try:
            # Decide where the image bytes come from:
            if image_file and image_file.filename:
                # User uploaded file
                file_content = image_file.read()
                filename = secure_filename(image_file.filename)
                mime_type = image_file.mimetype or "image/png"
            elif ai_image_base64:
                # AI-generated image from ChatGPT
                file_content = base64.b64decode(ai_image_base64)
                filename = "chatgpt-image.png"
                mime_type = "image/png"
            else:
                return jsonify({
                    "error": "Token image is required (no file, no AI image, no imported metadata)."
                }), 400

            if pool == "pump":
                # Pump.fun IPFS upload
                form_data = {
                    "name": name,
                    "symbol": symbol,
                    "description": description,
                    "twitter": twitter,
                    "telegram": telegram,
                    "website": website,
                    "showName": "true",
                }

                files = {"file": (filename, file_content, mime_type)}

                metadata_resp = requests.post(
                    "https://pump.fun/api/ipfs",
                    data=form_data,
                    files=files,
                    timeout=60,
                )

                if not metadata_resp.ok:
                    return jsonify({
                        "error": "Failed to upload metadata to pump.fun",
                        "status_code": metadata_resp.status_code,
                        "raw": metadata_resp.text[:500],
                    }), 502

                metadata_json = metadata_resp.json()
                metadata_uri = metadata_json.get("metadataUri")
                if not metadata_uri:
                    return jsonify({
                        "error": "pump.fun IPFS response missing metadataUri",
                        "raw": metadata_json,
                    }), 502

            elif pool == "bonk":
                # Bonk.fun: upload image, then metadata via letsbonk storage
                # 1) Upload image
                files = {"image": (filename, file_content, mime_type)}
                img_resp = requests.post(
                    "https://nft-storage.letsbonk22.workers.dev/upload/img",
                    files=files,
                    timeout=60,
                )
                if not img_resp.ok:
                    return jsonify({
                        "error": "Failed to upload image to Bonk storage",
                        "status_code": img_resp.status_code,
                        "raw": img_resp.text[:500],
                    }), 502

                img_uri = img_resp.text.strip()

                # 2) Upload metadata JSON
                meta_payload = {
                    "createdOn": "https://bonk.fun",
                    "description": description,
                    "image": img_uri,
                    "name": name,
                    "symbol": symbol,
                    "website": website,
                    "twitter": twitter,
                    "telegram": telegram,
                }

                meta_resp = requests.post(
                    "https://nft-storage.letsbonk22.workers.dev/upload/meta",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(meta_payload),
                    timeout=60,
                )
                if not meta_resp.ok:
                    return jsonify({
                        "error": "Failed to upload metadata to Bonk storage",
                        "status_code": meta_resp.status_code,
                        "raw": meta_resp.text[:500],
                    }), 502

                metadata_uri = meta_resp.text.strip()
                if not metadata_uri:
                    return jsonify({
                        "error": "Bonk metadata response missing URI",
                        "raw": meta_resp.text[:500],
                    }), 502

            else:
                return jsonify({"error": "Unsupported pool selected"}), 400

        except requests.RequestException as e:
            return jsonify(
                {"error": "Error uploading metadata", "details": str(e)}
            ), 500

    # ------------ 3. Launch multiple coins using PumpPortal ------------
    results = []

    for i in range(launch_count):
        try:
            # New mint for each coin
            mint_keypair = Keypair()
            mint_pubkey = str(mint_keypair.pubkey())
            mint_secret_str = str(mint_keypair)  # base58 secret for Lightning API

            token_metadata = {
                "name": name,
                "symbol": symbol,
                "uri": metadata_uri,
            }

            body = {
                "action": "create",
                "tokenMetadata": token_metadata,
                "mint": mint_secret_str,
                "denominatedInSol": "true",
                "amount": float(amount),  # same SOL for each token launch
                "slippage": 10,
                "priorityFee": 0.0005,
                "pool": pool,
                "isMayhemMode": "false",
            }

            resp = requests.post(
                f"https://pumpportal.fun/api/trade?api-key={PUMPPORTAL_API_KEY}",
                headers={"Content-Type": "application/json"},
                data=json.dumps(body),
                timeout=60,
            )

            print(f"PumpPortal status (launch {i+1}):", resp.status_code)
            print("PumpPortal raw body (first 500 chars):")
            print(resp.text[:500])

            try:
                payload = resp.json()
            except ValueError:
                results.append({
                    "index": i + 1,
                    "error": "PumpPortal returned non-JSON",
                    "status_code": resp.status_code,
                    "raw": resp.text[:500],
                })
                continue

            if not resp.ok:
                results.append({
                    "index": i + 1,
                    "error": "PumpPortal API error",
                    "status_code": resp.status_code,
                    "details": payload,
                })
                continue

            # Success for this launch (create)
            create_sig = payload.get("signature")
            launch_result = {
                "index": i + 1,
                "mint": mint_pubkey,
                "signature": create_sig,
                "pumpportal_response": payload,
                "pool": pool,
            }

            # ---------- Optional instant sell ----------
            if do_instant_sell:
                try:
                    # Delay before selling (5 seconds)
                    time.sleep(sell_delay_seconds)

                    sell_body = {
                        "action": "sell",
                        "mint": mint_pubkey,
                        "amount": "100%",        # sell all tokens in Lightning wallet
                        "denominatedInSol": "false",
                        "slippage": 10,
                        "priorityFee": 0.0005,
                        "pool": pool,
                    }

                    sell_resp = requests.post(
                        f"https://pumpportal.fun/api/trade?api-key={PUMPPORTAL_API_KEY}",
                        headers={"Content-Type": "application/json"},
                        data=json.dumps(sell_body),
                        timeout=60,
                    )

                    print(
                        f"Instant SELL status (launch {i+1}):",
                        sell_resp.status_code,
                    )
                    print("Instant SELL raw (first 500 chars):")
                    print(sell_resp.text[:500])

                    try:
                        sell_payload = sell_resp.json()
                    except ValueError:
                        launch_result["sell_error"] = {
                            "reason": "non-json",
                            "status_code": sell_resp.status_code,
                            "raw": sell_resp.text[:500],
                        }
                    else:
                        if sell_resp.ok:
                            launch_result["sell_signature"] = (
                                sell_payload.get("signature")
                                or sell_payload.get("txSignature")
                                or sell_payload.get("result")
                            )
                            launch_result["sell_response"] = sell_payload
                        else:
                            launch_result["sell_error"] = {
                                "status_code": sell_resp.status_code,
                                "details": sell_payload,
                            }

                except requests.RequestException as e:
                    launch_result["sell_error"] = {
                        "reason": "request_exception",
                        "details": str(e),
                    }

            # Record this launch
            results.append(launch_result)

        except requests.RequestException as e:
            results.append({
                "index": i + 1,
                "error": "Request to PumpPortal failed",
                "details": str(e),
            })
        except Exception as e:
            results.append({
                "index": i + 1,
                "error": "Unexpected error",
                "details": str(e),
            })

    # ------------ 4. Return list of all launches ------------
    any_success = any("mint" in r for r in results)

    return jsonify({
        "status": "success" if any_success else "failed",
        "results": results,
    })


# -----------------------------------------------------------
# Import existing token metadata (via Moralis + pump.fun IPFS)
# -----------------------------------------------------------
@app.post("/api/import-token")
def import_token():
    if not MORALIS_API_KEY:
        return jsonify(
            {"error": "Server misconfigured: missing MORALIS_API_KEY"}
        ), 500

    data = request.get_json(silent=True) or {}
    mint = data.get("mint", "").strip()

    if not mint:
        return jsonify({"error": "Missing mint address"}), 400

    # 1) Fetch token metadata (name, symbol, metaplex.metadataUri) from Moralis
    url = f"https://solana-gateway.moralis.io/token/mainnet/{mint}/metadata"

    try:
        resp = requests.get(
            url,
            headers={"X-API-Key": MORALIS_API_KEY},
            timeout=30,
        )
    except requests.RequestException as e:
        return jsonify({
            "error": "Failed to contact Moralis",
            "details": str(e),
        }), 502

    if not resp.ok:
        try:
            payload = resp.json()
        except ValueError:
            payload = {"raw": resp.text[:500]}
        return jsonify({
            "error": "Moralis metadata lookup failed",
            "status_code": resp.status_code,
            "details": payload,
        }), resp.status_code

    try:
        meta = resp.json()
    except ValueError:
        return jsonify({
            "error": "Moralis returned non-JSON response",
            "raw": resp.text[:500],
        }), 502

    name = meta.get("name")
    symbol = meta.get("symbol")
    metaplex = meta.get("metaplex") or {}
    metadata_uri = metaplex.get("metadataUri") or metaplex.get("metadata_uri")

    description = None
    twitter = None
    telegram = None
    website = None
    image_url = None

    # 2) If we have metadataUri, fetch the IPFS JSON (holds socials + image)
    if metadata_uri:
        try:
            ipfs_resp = requests.get(metadata_uri, timeout=30)
            if ipfs_resp.ok:
                try:
                    ipfs_json = ipfs_resp.json()
                    description = ipfs_json.get("description") or description
                    twitter = ipfs_json.get("twitter") or twitter
                    telegram = ipfs_json.get("telegram") or telegram
                    website = ipfs_json.get("website") or website
                    image_url = ipfs_json.get("image") or image_url
                    # Some tokens override name/symbol here too:
                    name = ipfs_json.get("name") or name
                    symbol = ipfs_json.get("symbol") or symbol
                except ValueError:
                    pass
        except requests.RequestException:
            pass

    return jsonify({
        "mint": mint,
        "name": name,
        "symbol": symbol,
        "description": description,
        "twitter": twitter,
        "telegram": telegram,
        "website": website,
        "metadata_uri": metadata_uri,
        "image": image_url,
    })


# -----------------------------------------------------------
# Run app
# -----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
