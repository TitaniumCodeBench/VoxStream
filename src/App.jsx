import { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [text, setText] = useState("");
  const [isServerRunning, setIsServerRunning] = useState(false);
  const [status, setStatus] = useState({
    is_recording: false,
    is_running: false,
    is_shut_down: true,
    is_initializing: false
  });
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const [isCopying, setIsCopying] = useState(false);

  const textWs = useRef(null);
  const statusWs = useRef(null);
  const scrollRef = useRef(null);
  const reconnectTimeout = useRef(null);

  useEffect(() => {
    checkServer();
    const interval = setInterval(checkServer, 5000);
    return () => {
      clearInterval(interval);
      if (textWs.current) textWs.current.close();
      if (statusWs.current) statusWs.current.close();
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [text]);

  const checkServer = async () => {
    try {
      const response = await fetch('http://localhost:8000/');
      if (response.ok) {
        setIsServerRunning(true);
        if (!textWs.current || textWs.current.readyState === WebSocket.CLOSED) {
          connectWebSockets();
        }
      } else {
        throw new Error();
      }
    } catch (error) {
      setIsServerRunning(false);
      setConnectionStatus("disconnected");
      setStatus(prev => ({ ...prev, is_shut_down: true, is_initializing: false }));
    }
  };

  const connectWebSockets = () => {
    if (connectionStatus === "connecting") return;
    setConnectionStatus("connecting");

    // Transcription WebSocket
    if (textWs.current) textWs.current.close();
    textWs.current = new WebSocket("ws://localhost:8000/ws");

    textWs.current.onopen = () => {
      console.log("Transcription WS: Connected");
      setConnectionStatus("connected");
    };

    textWs.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "transcription" && data.text) {
          setText(prev => (prev ? prev + " " + data.text : data.text));
        }
      } catch (e) {
        console.error("Failed to parse transcription message", e);
      }
    };

    textWs.current.onclose = () => {
      console.log("Transcription WS: Disconnected");
      setConnectionStatus("disconnected");
    };

    // Status WebSocket
    if (statusWs.current) statusWs.current.close();
    statusWs.current = new WebSocket("ws://localhost:8000/status-ws");

    statusWs.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "status" && data.status) {
          setStatus(data.status);
        }
      } catch (e) {
        console.error("Failed to parse status message", e);
      }
    };
  };

  const handleAction = async (action) => {
    try {
      const response = await fetch(`http://localhost:8000/${action}`);
      if (response.ok) {
        await checkServer();
      }
    } catch (err) {
      console.error(`Failed to ${action}:`, err);
    }
  };

  const clearText = () => setText("");

  const copyToClipboard = () => {
    navigator.clipboard.writeText(text);
    setIsCopying(true);
    setTimeout(() => setIsCopying(false), 2000);
  };

  return (
    <div className="app-container">
      <div className="glass-blob blob-1"></div>
      <div className="glass-blob blob-2"></div>

      <div className="main-layout">
        <aside className="sidebar">
          <div className="brand">
            <div className="logo-icon">
              <div className="outer-ring"></div>
              <div className="inner-ring"></div>
              <div className="core"></div>
            </div>
            <h1>VOX<span>STREAM</span></h1>
          </div>

          <nav className="controls">
            <div className="control-group">
              <label>Engine Control</label>
              <button
                className={`btn-action ${(!status.is_shut_down || status.is_initializing) ? 'disabled' : ''}`}
                onClick={() => handleAction('start')}
                disabled={!status.is_shut_down || status.is_initializing}
              >
                {status.is_initializing ? 'Warming Up...' : 'Initialize Engine'}
              </button>
              <button
                className={`btn-action danger ${status.is_shut_down ? 'disabled' : ''}`}
                onClick={() => handleAction('shutdown')}
                disabled={status.is_shut_down}
              >
                Kill Session
              </button>
            </div>

            <div className="control-group">
              <label>System Monitor</label>
              <div className="stat-row">
                <span>Server</span>
                <span className={`badge ${isServerRunning ? 'online' : 'offline'}`}>
                  {isServerRunning ? 'ONLINE' : 'OFFLINE'}
                </span>
              </div>
              <div className="stat-row">
                <span>WebSocket</span>
                <span className={`badge ${connectionStatus}`}>
                  {connectionStatus.toUpperCase()}
                </span>
              </div>
            </div>
          </nav>

          <div className="footer-sidebar">
            <p>v2.1.0 Premium Access</p>
          </div>
        </aside>

        <section className="content">
          <header className="content-header">
            <div className="status-cards">
              <div className={`status-card ${status.is_recording ? 'active-rec' : ''} ${status.is_initializing ? 'initializing' : ''}`}>
                <div className="card-icon rec">●</div>
                <div className="card-info">
                  <span className="card-label">Recorder</span>
                  <span className="card-value">
                    {status.is_initializing ? 'INITIALIZING' : status.is_recording ? 'RECORDING' : 'READY'}
                  </span>
                </div>
                {status.is_recording && (
                  <div className="waveform">
                    <div className="bar"></div><div className="bar"></div><div className="bar) "></div><div className="bar"></div>
                  </div>
                )}
              </div>

              <div className={`status-card ${status.is_running ? 'active-run' : ''} ${status.is_initializing ? 'initializing' : ''}`}>
                <div className="card-icon run">▶</div>
                <div className="card-info">
                  <span className="card-label">Engine</span>
                  <span className="card-value">
                    {status.is_initializing ? 'INITIALIZING' : status.is_running ? 'ACTIVE' : 'IDLE'}
                  </span>
                </div>
              </div>
            </div>
          </header>

          <main className="transcript-area">
            <div className="glass-panel">
              <div className="panel-header">
                <h3>Live Transcription Output</h3>
                <div className="panel-actions">
                  <button onClick={copyToClipboard} className={`icon-btn ${isCopying ? 'copied' : ''}`} title="Copy Text">
                    {isCopying ? '✓' : '⎘'}
                  </button>
                  <button onClick={clearText} className={`icon-btn icon-btn-del`} title="Clear All">🗑</button>
                </div>
              </div>
              <div className="text-viewport" ref={scrollRef}>
                {text ? (
                  <p className="transcribed-text">{text}</p>
                ) : (
                  <div className="empty-state">
                    <div className="scanner"></div>
                    <p>Awaiting...</p>
                  </div>
                )}
              </div>
            </div>
          </main>
        </section>
      </div>
    </div>
  );
}

export default App;
