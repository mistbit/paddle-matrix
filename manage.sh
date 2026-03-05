#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${ROOT_DIR}/.paddle-matrix.pid"
LOG_FILE="${ROOT_DIR}/.paddle-matrix.log"
APP_MODULE="app.main:app"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-}"
DOCKER_MODE="${DOCKER_MODE:-auto}"
DOCKER_BIN=""
DOCKER_USE_PLUGIN="0"
DOCKER_SERVICE="subtitle-ocr"

is_supported_python() {
  local py="$1"
  local version
  local major
  local minor

  version="$("${py}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)"
  if [[ -z "${version}" ]]; then
    return 1
  fi

  major="${version%%.*}"
  minor="${version##*.}"
  if [[ "${major}" != "3" ]]; then
    return 1
  fi

  if (( minor >= 9 && minor <= 12 )); then
    return 0
  fi

  return 1
}

resolve_runtime() {
  if [[ -x "${VENV_PYTHON}" ]]; then
    PYTHON_BIN="${VENV_PYTHON}"
    return
  fi

  if [[ -n "${PYTHON_BIN}" ]] && is_supported_python "${PYTHON_BIN}"; then
    return
  fi

  PYTHON_BIN=""
  for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
    local path
    path="$(command -v "${cmd}" || true)"
    if [[ -n "${path}" ]] && is_supported_python "${path}"; then
      PYTHON_BIN="${path}"
      break
    fi
  done
}

runtime_has_dependencies() {
  if [[ -z "${PYTHON_BIN}" ]]; then
    return 1
  fi

  "${PYTHON_BIN}" -c "import uvicorn, fastapi, pydantic_settings, paddleocr" >/dev/null 2>&1
}

resolve_docker_runtime() {
  if [[ -n "${DOCKER_BIN}" ]]; then
    return
  fi

  local docker_path
  docker_path="$(command -v docker || true)"
  if [[ -n "${docker_path}" ]] && "${docker_path}" compose version >/dev/null 2>&1; then
    DOCKER_BIN="${docker_path}"
    DOCKER_USE_PLUGIN="1"
    return
  fi

  local docker_compose_path
  docker_compose_path="$(command -v docker-compose || true)"
  if [[ -n "${docker_compose_path}" ]]; then
    DOCKER_BIN="${docker_compose_path}"
    DOCKER_USE_PLUGIN="0"
    return
  fi
}

docker_available() {
  resolve_docker_runtime
  [[ -n "${DOCKER_BIN}" ]]
}

run_compose() {
  if ! docker_available; then
    return 1
  fi

  if [[ "${DOCKER_USE_PLUGIN}" == "1" ]]; then
    "${DOCKER_BIN}" compose -f "${ROOT_DIR}/docker-compose.yml" "$@"
  else
    "${DOCKER_BIN}" -f "${ROOT_DIR}/docker-compose.yml" "$@"
  fi
}

is_docker_running() {
  if ! docker_available; then
    return 1
  fi

  run_compose ps -q "${DOCKER_SERVICE}" 2>/dev/null | grep -q .
}

start_docker() {
  if ! docker_available; then
    echo "未检测到 Docker，无法使用工程内运行环境"
    return 1
  fi

  run_compose up -d
  if is_docker_running; then
    echo "Docker 服务启动成功"
    echo "访问地址: http://127.0.0.1:${PORT}"
    return 0
  fi

  echo "Docker 服务启动失败"
  return 1
}

stop_python_service() {
  local pid
  pid="$(cat "${PID_FILE}")"
  kill "${pid}" >/dev/null 2>&1 || true

  for _ in {1..20}; do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      rm -f "${PID_FILE}"
      echo "本地服务已停止"
      return 0
    fi
    sleep 0.2
  done

  kill -9 "${pid}" >/dev/null 2>&1 || true
  rm -f "${PID_FILE}"
  echo "本地服务已强制停止"
}

stop_docker() {
  if ! is_docker_running; then
    return 1
  fi

  run_compose down >/dev/null 2>&1 || true
  echo "Docker 服务已停止"
  return 0
}

install_dependencies() {
  local bootstrap_python
  local bootstrap_version
  local venv_version
  for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
    bootstrap_python="$(command -v "${cmd}" || true)"
    if [[ -n "${bootstrap_python}" ]] && is_supported_python "${bootstrap_python}"; then
      break
    fi
  done

  if [[ -z "${bootstrap_python:-}" ]]; then
    echo "未找到兼容的 Python 版本（需要 3.9~3.12），无法自动安装依赖"
    echo "可执行：brew install python@3.11"
    return 1
  fi

  if [[ ! -f "${ROOT_DIR}/requirements.txt" ]]; then
    echo "未找到 requirements.txt，无法自动安装依赖"
    return 1
  fi

  bootstrap_version="$("${bootstrap_python}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
  if [[ -x "${VENV_PYTHON}" ]]; then
    venv_version="$("${VENV_PYTHON}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" || true)"
    if [[ -n "${venv_version}" && "${venv_version}" != "${bootstrap_version}" ]]; then
      rm -rf "${ROOT_DIR}/.venv"
    fi
  fi

  if [[ ! -x "${VENV_PYTHON}" ]]; then
    if ! "${bootstrap_python}" -m venv "${ROOT_DIR}/.venv"; then
      echo "创建虚拟环境失败"
      return 1
    fi
  fi

  PYTHON_BIN="${VENV_PYTHON}"
  if ! "${PYTHON_BIN}" -m pip install --upgrade pip; then
    echo "更新 pip 失败"
    return 1
  fi

  if ! "${PYTHON_BIN}" -m pip install -r "${ROOT_DIR}/requirements.txt"; then
    echo "自动安装依赖失败，当前 Python 版本可能与 paddlepaddle 不兼容"
    "${PYTHON_BIN}" -V || true
    return 1
  fi

  resolve_runtime
  return 0
}

preflight() {
  resolve_runtime

  if runtime_has_dependencies; then
    return 0
  fi

  echo "检测到依赖未就绪，开始自动安装..."
  install_dependencies || return 1

  if runtime_has_dependencies; then
    return 0
  fi

  echo "自动安装完成，但依赖仍不完整"
  return 1
}

is_running() {
  if [[ ! -f "${PID_FILE}" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "${PID_FILE}")"
  if [[ -z "${pid}" ]]; then
    return 1
  fi

  if kill -0 "${pid}" >/dev/null 2>&1; then
    return 0
  fi

  rm -f "${PID_FILE}"
  return 1
}

start() {
  if is_running; then
    local pid
    pid="$(cat "${PID_FILE}")"
    echo "服务已启动，PID: ${pid}"
    return 0
  fi

  if is_docker_running; then
    echo "Docker 服务已启动"
    return 0
  fi

  cd "${ROOT_DIR}"
  if [[ "${DOCKER_MODE}" == "docker" ]]; then
    start_docker
    return $?
  fi

  if ! preflight; then
    if [[ "${DOCKER_MODE}" == "python" ]]; then
      return 1
    fi
    echo "本地依赖不可用，尝试使用 Docker 运行环境..."
    start_docker
    return $?
  fi

  if [[ -n "${PYTHON_BIN}" ]]; then
    nohup "${PYTHON_BIN}" -m uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" >>"${LOG_FILE}" 2>&1 &
  else
    echo "未找到可用 Python，请安装后重试"
    return 1
  fi
  local pid=$!
  echo "${pid}" > "${PID_FILE}"

  sleep 1
  if kill -0 "${pid}" >/dev/null 2>&1; then
    echo "服务启动成功，PID: ${pid}"
    echo "访问地址: http://127.0.0.1:${PORT}"
    return 0
  fi

  rm -f "${PID_FILE}"
  echo "服务启动失败，请查看日志: ${LOG_FILE}"
  return 1
}

stop() {
  local stopped="0"

  if is_running; then
    stop_python_service
    stopped="1"
  fi

  if is_docker_running; then
    stop_docker || true
    stopped="1"
  fi

  if [[ "${stopped}" == "0" ]]; then
    echo "服务未运行"
  fi
}

status() {
  local has_status="0"

  if is_running; then
    local pid
    pid="$(cat "${PID_FILE}")"
    echo "本地服务运行中，PID: ${pid}"
    has_status="1"
  fi

  if is_docker_running; then
    echo "Docker 服务运行中"
    has_status="1"
  fi

  if [[ "${has_status}" == "0" ]]; then
    echo "服务未运行"
  fi
}

logs() {
  if is_docker_running; then
    run_compose logs -f --tail=200 "${DOCKER_SERVICE}"
    return
  fi
  touch "${LOG_FILE}"
  tail -n 200 -f "${LOG_FILE}"
}

usage() {
  echo "用法: $0 {start|stop|restart|status|logs}"
  echo "可选环境变量: DOCKER_MODE=auto|python|docker"
}

case "${1:-}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
    stop
    start
    ;;
  status)
    status
    ;;
  logs)
    logs
    ;;
  *)
    usage
    exit 1
    ;;
esac
