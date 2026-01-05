import { useState, useEffect } from 'react'
import "./App.css"

function App() {
  // States
  const [Text, setText] = useState("")
  const [is_recording, setIs_Recording] = useState(false)
  const [is_running, setIs_Running] = useState(false)
  const [is_shut_down, setIs_Shut_Down] = useState(false)
  const [is_server_running, setIs_Server_Running] = useState(false)

  useEffect(() => {
    check_server()
  }, [])


  const check_server = async () => {
    try {
      const res = await fetch("http://localhost:8000/")
      if (res.ok) {
        console.log("Server is running")
        setIs_Server_Running(true)
        transcribe_text()
        status()

      } else {
        console.log("Server error")
      }
    } catch {
      console.log("Server is not running")
      setIs_Server_Running(false)
    }
  }

  const transcribe_text = async () => {
    const text = new WebSocket("ws://localhost:8000/ws")
    text.onopen = () => {
      console.log("Connected to server")
    }
    text.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setText(prev => prev + data.text)
    }
    text.onerror = (error) => {
      console.log(error)
      check_server()
    }
  }

  const status = async () => {
    const status = new WebSocket("ws://localhost:8000/status-ws")
    status.onopen = () => {
      console.log("Connected to server")
    }
    status.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setIs_Recording(data.status.is_recording)
      setIs_Running(data.status.is_running)
      setIs_Shut_Down(data.status.is_shut_down)
    }
    status.onerror = (error) => {
      console.log(error)
      check_server()
    }
  }





  const clear_text = () => {
    setText("")
  }

  if (!is_server_running) {
    return (
      <div className="server_error">
        <h1>Server is not running</h1>
        <p>Please start the backend server to use the application.</p>
      </div>
    )
  }
  return (
    <div className="wrapper">
      <div className="navbar">
        <span className="brand">S T T</span>
        <div className="status_container">
          <div className="status_item">
            <div className={`dot ${is_recording ? 'dot_red' : 'dot_gray'}`}></div>
            <span>{is_recording ? "RECORDING" : "MIC IDLE"}</span>
          </div>
          <div className="status_item">
            <div className={`dot ${is_running ? 'dot_green' : 'dot_gray'}`}></div>
            <span>{is_running ? "RUNNING" : "STANDBY"}</span>
          </div>
          {is_shut_down && (
            <div className="status_item">
              <div className="dot dot_red"></div>
              <span>SHUTTING DOWN</span>
            </div>
          )}
        </div>
      </div>

      <div className="body_wrapper">
        <h3>Live Transcription</h3>
        <div className="transcribe_text_wrapper">
          <span className="transcribe_text">{Text}</span>
        </div>
        <div className="controls">
          <button onClick={clear_text} title="Clear All Text" className="button">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18"></path>
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
            </svg>
            Clear Transcription
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
