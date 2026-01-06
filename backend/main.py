import logging
import asyncio
import time
import json
import uvicorn
from pathlib import Path
from RealtimeSTT import AudioToTextRecorder
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- LOGGING CONFIGURATION ---
log_level = logging.INFO
console_log_format = "%(asctime)s - %(levelname)s - %(message)s"
console_log_datefmt = "%H:%M:%S"
file_log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# Console Log Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(console_log_format, console_log_datefmt))
console_handler.setLevel(log_level)
logger.addHandler(console_handler)

# File Log Handler
log_file_path = Path(__file__).parent / "server.log"
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(logging.Formatter(file_log_format))
file_handler.setLevel(log_level)
logger.addHandler(file_handler)

# --- LOAD CONFIGURATION ---
config_path = Path(__file__).parent / "config_.json"
try:
    with open(config_path, "r") as f:
        config = json.load(f)
except FileNotFoundError:
    logger.error(f"Configuration file not found at {config_path}. Using defaults.")
    config = {"MODEL": "base.en", "LANGUAGE": "en"}
except Exception as e:
    logger.error(f"Error loading config: {e}. Using defaults.")
    config = {"MODEL": "base.en", "LANGUAGE": "en"}

MODEL = config.get("MODEL", "base.en")
LANGUAGE = config.get("LANGUAGE", "en")

# --- FASTAPI APP ---
app = FastAPI(debug=False)
recorder = None
is_initializing = False

origins = [
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def data_formater(message_, type_):
    return {"message": message_, "type": type_, "time": time.time()}


def initialize_recorder():
    global recorder, is_initializing
    is_initializing = True
    try:
        recorder = AudioToTextRecorder(
            model=MODEL,
            language=LANGUAGE,
            no_log_file=True,
            spinner=False,
            silero_sensitivity=0.6,
            silero_deactivity_detection=True,
            webrtc_sensitivity=2,
            post_speech_silence_duration=0.8,
            min_length_of_recording=1.0,
            silero_use_onnx=True,
        )
        logger.info("RealTimeSTT Engine initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize recorder: {e}")
        return False
    finally:
        is_initializing = False


@app.on_event("startup")
async def startup():
    logger.info("Server starting... initializing STT Engine in background")
    # Run initialization in the background so the API stays responsive
    asyncio.create_task(asyncio.to_thread(initialize_recorder))
    logger.info("Background initialization task scheduled")


@app.get("/")
def root():
    return data_formater("STT System Backend Online", "info")


@app.get("/shutdown")
def shutdown():
    global recorder
    if recorder is None:
        return data_formater("Engine already stopped", "info")
    logger.info("Shutting down RealTimeSTT Engine")
    recorder.shutdown()
    recorder = None
    logger.info("Engine stopped")
    return data_formater("Engine stopped", "info")


@app.get("/start")
def start():
    global recorder
    if recorder is not None:
        return data_formater("Engine already running", "info")
    logger.info("Initializing Engine...")
    if initialize_recorder():
        return data_formater("Engine started", "info")
    else:
        return data_formater("Failed to start engine", "error")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Transcription WebSocket connected")
    last_text = ""
    try:
        while True:
            if recorder is None:
                await websocket.send_json(
                    {"text": "Engine is offline", "type": "error", "time": time.time()}
                )
                break

            text = await asyncio.to_thread(recorder.text)
            if text:
                text = text.strip()
                if text and text != last_text:
                    await websocket.send_json(
                        {"text": text, "type": "transcription", "time": time.time()}
                    )
                    last_text = text
    except WebSocketDisconnect:
        logger.info("Transcription WebSocket disconnected")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
    finally:
        logger.info("Cleaning up Transcription WebSocket")


@app.websocket("/status-ws")
async def status_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Status WebSocket connected")
    try:
        while True:
            status = {
                "is_recording": recorder.is_recording if recorder else False,
                "is_running": recorder.is_running if recorder else False,
                "is_shut_down": recorder is None and not is_initializing,
                "is_initializing": is_initializing,
            }
            await websocket.send_json(
                {"status": status, "type": "status", "time": time.time()}
            )
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Status WebSocket disconnected")
    except Exception as e:
        logger.error(f"Status error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
