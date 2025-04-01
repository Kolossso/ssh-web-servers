document.addEventListener("DOMContentLoaded", () => {
    // Инициализация Socket.IO
    const socket = io()
    const logContent = document.getElementById("log-content")
    const autoScroll = document.getElementById("auto-scroll")
    const statusLight = document.getElementById("status-light")
    const statusText = document.getElementById("status-text")
    const startServerBtn = document.getElementById("start-server")
    const stopServerBtn = document.getElementById("stop-server")
    const updateServerBtn = document.getElementById("update-server")
    const clearLogsBtn = document.getElementById("clear-logs")
    const commandInput = document.getElementById("command-input")
    const sendCommandBtn = document.getElementById("send-command")
    const copyConnectBtn = document.getElementById("copy-connect")
    const serverIp = document.getElementById("server-ip").textContent
  
    // Максимальное количество строк в логе (для производительности)
    const MAX_LOG_LINES = 1000
  
    // Обработка обновлений логов
    socket.on("log_update", (data) => {
      // Очищаем сообщение о загрузке, если это первое обновление
      if (logContent.querySelector(".text-muted")) {
        logContent.innerHTML = ""
      }
  
      // Добавляем новые строки
      data.lines.forEach((line) => {
        const logLine = document.createElement("div")
        logLine.className = "log-line"
        logLine.innerHTML = line
        logContent.appendChild(logLine)
      })
  
      // Ограничиваем количество строк для производительности
      while (logContent.children.length > MAX_LOG_LINES) {
        logContent.removeChild(logContent.firstChild)
      }
  
      // Прокручиваем вниз, если включена автопрокрутка
      if (autoScroll.checked) {
        logContent.scrollTop = logContent.scrollHeight
      }
  
      // Обновляем статус сервера
      updateServerStatus()
    })
  
    // Обработка ошибок логов
    socket.on("log_error", (data) => {
      const errorLine = document.createElement("div")
      errorLine.className = "log-line text-danger"
      errorLine.textContent = `Ошибка: ${data.error}`
      logContent.appendChild(errorLine)
    })
  
    // Функция для обновления статуса сервера
    function updateServerStatus() {
      fetch("/api/status")
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "running") {
            statusLight.className = "status-light status-on"
            statusText.textContent = "Запущен"
          } else {
            statusLight.className = "status-light status-off"
            statusText.textContent = "Остановлен"
          }
        })
        .catch((error) => console.error("Ошибка при получении статуса:", error))
    }
  
    // Запуск сервера
    startServerBtn.addEventListener("click", () => {
      showToast("Запуск сервера...")
      fetch("/api/start", { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
          showToast(data.message)
          setTimeout(updateServerStatus, 2000)
        })
        .catch((error) => {
          console.error("Ошибка при запуске сервера:", error)
          showToast("Ошибка при запуске сервера", "danger")
        })
    })
  
    // Остановка сервера
    stopServerBtn.addEventListener("click", () => {
      showToast("Остановка сервера...")
      fetch("/api/stop", { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
          showToast(data.message)
          setTimeout(updateServerStatus, 2000)
        })
        .catch((error) => {
          console.error("Ошибка при остановке сервера:", error)
          showToast("Ошибка при остановке сервера", "danger")
        })
    })
  
    // Обновление сервера
    updateServerBtn.addEventListener("click", () => {
      showToast("Обновление сервера...")
      fetch("/api/update", { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
          showToast(data.message)
        })
        .catch((error) => {
          console.error("Ошибка при обновлении сервера:", error)
          showToast("Ошибка при обновлении сервера", "danger")
        })
    })
  
    // Очистка логов
    clearLogsBtn.addEventListener("click", () => {
      fetch("/api/clear_logs", { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
          logContent.innerHTML = ""
          showToast(data.message)
        })
        .catch((error) => {
          console.error("Ошибка при очистке логов:", error)
          showToast("Ошибка при очистке логов", "danger")
        })
    })
  
    // Отправка команды
    function sendCommand() {
      const command = commandInput.value.trim()
      if (!command) return
  
      fetch("/api/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ command: command }),
      })
        .then((response) => response.json())
        .then((data) => {
          showToast(data.message)
          commandInput.value = ""
        })
        .catch((error) => {
          console.error("Ошибка при отправке команды:", error)
          showToast("Ошибка при отправке команды", "danger")
        })
    }
  
    // Обработчик кнопки отправки команды
    sendCommandBtn.addEventListener("click", sendCommand)
  
    // Обработчик нажатия Enter в поле ввода команды
    commandInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        sendCommand()
      }
    })
  
    // Копирование команды подключения
    copyConnectBtn.addEventListener("click", () => {
      const connectCommand = `connect ${serverIp}:27015`
      navigator.clipboard
        .writeText(connectCommand)
        .then(() => {
          showToast("Команда подключения скопирована в буфер обмена")
        })
        .catch((err) => {
          console.error("Ошибка при копировании:", err)
          showToast("Не удалось скопировать команду", "danger")
        })
    })
  
    // Функция для отображения уведомлений
    function showToast(message, type = "success") {
      // Создаем элемент уведомления
      const toast = document.createElement("div")
      toast.className = `toast align-items-center text-white bg-${type} border-0`
      toast.setAttribute("role", "alert")
      toast.setAttribute("aria-live", "assertive")
      toast.setAttribute("aria-atomic", "true")
  
      toast.innerHTML = `
              <div class="d-flex">
                  <div class="toast-body">
                      ${message}
                  </div>
                  <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
              </div>
          `
  
      // Добавляем уведомление на страницу
      if (!document.querySelector(".toast-container")) {
        const toastContainer = document.createElement("div")
        toastContainer.className = "toast-container position-fixed bottom-0 end-0 p-3"
        document.body.appendChild(toastContainer)
      }
  
      const toastContainer = document.querySelector(".toast-container")
      toastContainer.appendChild(toast)
  
      // Инициализируем и показываем уведомление
      const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 3000,
      })
      bsToast.show()
  
      // Удаляем уведомление после скрытия
      toast.addEventListener("hidden.bs.toast", () => {
        toast.remove()
      })
    }
  
    // Инициализация: обновляем статус сервера
    updateServerStatus()
  })
  
  