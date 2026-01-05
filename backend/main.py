import uvicorn
import asyncio
import json
import logging
from pathlib import Path
from typing import Set
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from RealtimeSTT import AudioToTextRecorder
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename="server.log",
    filemode="w",
    format="%(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=5)

# Global recorder instance
recorder = None

# Connection managers for WebSocket clients
transcription_clients: Set[WebSocket] = set()

# Load configuration
config_path = Path(__file__).parent / "config_.js"
try:
    with open(config_path) as config_file:
        config_data = json.load(config_file)
    MODEL = config_data.get("MODEL", "base.en")
    LANGUAGE = config_data.get("LANGUAGE", "en")
    logger.info(f"Configuration loaded: MODEL={MODEL}, LANGUAGE={LANGUAGE}")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    MODEL = "base.en"
    LANGUAGE = "en"


# Initialize FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global recorder

    # Startup: Initialize the recorder
    try:
        logger.info("Initializing AudioToTextRecorder...")
        recorder = AudioToTextRecorder(
            model=MODEL,
            language=LANGUAGE,
            silero_sensitivity=0.6,
            silero_deactivity_detection=True,
            webrtc_sensitivity=2,
            post_speech_silence_duration=0.8,
            min_length_of_recording=1.0,
            silero_use_onnx=True,
        )
        logger.info("Recorder initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize recorder: {e}")
        recorder = None

    yield

    # Shutdown: Clean up resources
    if recorder:
        try:
            logger.info("Shutting down recorder...")
            recorder.shutdown()
            logger.info("Recorder shutdown complete")
        except Exception as e:
            logger.error(f"Error during recorder shutdown: {e}")

    # Close all WebSocket connections
    for client in transcription_clients.copy():
        await client.close()

    executor.shutdown(wait=True)


app = FastAPI(title="STT System API", version="1.0.0", lifespan=lifespan)

# CORS middleware
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_recorder_status():
    """Get the current status of the recorder"""
    if not recorder:
        return {
            "is_recording": False,
            "is_running": False,
            "is_shut_down": True,
            "error": "Recorder not initialized",
        }

    try:
        return {
            "is_recording": recorder.is_recording,
            "is_running": recorder.is_running,
            "is_shut_down": recorder.is_shut_down,
        }
    except Exception as e:
        logger.error(f"Error getting recorder status: {e}")
        return {
            "is_recording": False,
            "is_running": False,
            "is_shut_down": True,
            "error": str(e),
        }


async def get_transcription():
    """Get transcription text in a non-blocking way"""
    if not recorder:
        return None

    loop = asyncio.get_running_loop()
    try:
        text = await loop.run_in_executor(executor, recorder.text)
        return text
    except KeyboardInterrupt:
        logger.info("Shutting down recorder...")
        recorder.shutdown()
        logger.info("Recorder shutdown complete")
    except Exception as e:
        logger.error(f"Error getting transcription: {e}")
        return None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "recorder_initialized": recorder is not None,
        "active_transcription_clients": len(transcription_clients),
    }


@app.get("/status")
async def get_status():
    """Get current recorder status via HTTP"""
    return {"status": get_recorder_status()}


@app.websocket("/ws")
async def transcribe_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time transcription"""
    await websocket.accept()
    transcription_clients.add(websocket)
    logger.info(
        f"New transcription client connected. Total clients: {len(transcription_clients)}"
    )

    if not recorder:
        await websocket.send_json(
            {"error": "Recorder not initialized", "type": "error"}
        )
        transcription_clients.discard(websocket)
        return

    # Track last sent text to avoid duplicates
    last_text = ""

    try:
        while True:
            # Get transcription text
            text = await get_transcription()

            # Only send if text is new and different from last sent
            if text and text.strip() and text.strip() != last_text:
                await websocket.send_json(
                    {
                        "text": text.strip(),
                        "type": "transcription",
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                )
                logger.info(f"Sent transcription: {text.strip()}")
                last_text = text.strip()

            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info("Transcription client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error in transcription endpoint: {repr(e)}")
        try:
            await websocket.send_json({"error": str(e), "type": "error"})
        except:
            pass
    finally:
        transcription_clients.discard(websocket)
        logger.info(
            f"Transcription client removed. Remaining clients: {len(transcription_clients)}"
        )


@app.websocket("/status-ws")
async def status_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time recorder status updates"""
    await websocket.accept()
    logger.info("Status client connected")

    try:
        while True:
            # Get current recorder status
            status = get_recorder_status()

            # Send status to client
            await websocket.send_json(
                {
                    "status": status,
                    "type": "status",
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            # Send status updates every 4000ms
            await asyncio.sleep(4)
    except WebSocketDisconnect:
        logger.info("Status client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error in status endpoint: {repr(e)}")
        try:
            await websocket.send_json({"error": str(e), "type": "error"})
        except:
            pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
