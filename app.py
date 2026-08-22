import asyncio
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()

# ==========================================
# 1. 메인 웹소켓 관리자 (기사님/관리자 간 실시간 통신)
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# 데이터 저장 구조
orders_db: Dict[int, dict] = {}
drivers_status: Dict[int, str] = {i: "대기중" for i in range(1, 6)} # 기사 1~5번
order_counter = 1

class OrderCreate(BaseModel):
    pickup: str
    destination: str
    fee: int

# ==========================================
# 2. 라우팅 (자동 이동 및 페이지)
# ==========================================

# [수정된 부분] 기본 주소 접속 시 기사님 페이지로 자동 이동
@app.get("/")
async def root():
    return RedirectResponse(url="/driver")

# 관리자 웹 페이지
@app.get("/admin", response_class=HTMLResponse)
async def get_admin_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>목포 퀵서비스 - 관리자 관제 시스템</title>
        <style>
            body { font-family: 'Noto Sans KR', sans-serif; margin: 0; padding: 20px; background-color: #f4f6f9; }
            h1 { color: #333; text-align: center; }
            .container { display: flex; gap: 20px; flex-wrap: wrap; }
            .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); flex: 1; min-width: 300px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 5px; }
            button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 5px; font-size: 16px; font-weight: bold; cursor: pointer; }
            button:hover { background: #0056b3; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border-bottom: 1px solid #eee; padding: 10px; text-align: center; }
            th { background-color: #f8f9fa; }
            .badge { padding: 4px 8px; border-radius: 4px; color: white; font-size: 12px; font-weight: bold; }
            .badge-waiting { background-color: #ffc107; color: #333; }
            .badge-accepted { background-color: #28a745; }
            .badge-completed { background-color: #6c757d; }
        </style>
    </head>
    <body>
        <h1>📦 목포 퀵 관제 센터</h1>
        <div class="container">
            <!-- 오더 접수 폼 -->
            <div class="card">
                <h2>신규 오더 접수</h2>
                <div class="form-group">
                    <label>출발지</label>
                    <input type="text" id="pickup" placeholder="예: 평화광장 파스쿠찌">
                </div>
                <div class="form-group">
                    <label>도착지</label>
                    <input type="text" id="destination" placeholder="예: 목포역 광장">
                </div>
                <div class="form-group">
                    <label>요금 (원)</label>
                    <input type="number" id="fee" placeholder="예: 8000" step="1000">
                </div>
                <button onclick="createOrder()">오더 등록 및 기사 발송</button>
            </div>

            <!-- 기사 현황 -->
            <div class="card">
                <h2>기사 실시간 상태 (1~5번)</h2>
                <table>
                    <thead>
                        <tr><th>기사 번호</th><th>현재 상태</th></tr>
                    </thead>
                    <tbody id="driver-list"></tbody>
                </table>
            </div>
        </div>

        <!-- 전체 오더 리스트 -->
        <div class="card" style="margin-top: 20px;">
            <h2>실시간 오더 현황</h2>
            <table>
                <thead>
                    <tr>
                        <th>번호</th>
                        <th>출발지</th>
                        <th>도착지</th>
                        <th>요금</th>
                        <th>상태</th>
                        <th>담당 기사</th>
                    </tr>
                </thead>
                <tbody id="order-list"></tbody>
            </table>
        </div>

        <script>
            const ws = new WebSocket(`wss://${location.host}/ws`);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'INIT' || data.type === 'UPDATE') {
                    renderOrders(data.orders);
                    renderDrivers(data.drivers);
                }
            };

            async function createOrder() {
                const pickup = document.getElementById('pickup').value;
                const destination = document.getElementById('destination').value;
                const fee = parseInt(document.getElementById('fee').value);

                if (!pickup || !destination || !fee) {
                    alert(' 모든 항목을 입력해 주세요.');
                    return;
                }

                await fetch('/api/orders', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pickup, destination, fee })
                });

                document.getElementById('pickup').value = '';
                document.getElementById('destination').value = '';
                document.getElementById('fee').value = '';
            }

            function renderOrders(orders) {
                const tbody = document.getElementById('order-list');
                tbody.innerHTML = '';
                Object.values(orders).reverse().forEach(o => {
                    let statusBadge = `<span class="badge badge-waiting">접수대기</span>`;
                    if (o.status === '배차완료') statusBadge = `<span class="badge badge-accepted">배차완료</span>`;
                    if (o.status === '배달완료') statusBadge = `<span class="badge badge-completed">배달완료</span>`;

                    tbody.innerHTML += `
                        <tr>
                            <td>${o.id}</td>
                            <td>${o.pickup}</td>
                            <td>${o.destination}</td>
                            <td>${o.fee.toLocaleString()}원</td>
                            <td>${statusBadge}</td>
                            <td>${o.driver_id ? o.driver_id + '번 기사' : '-'}</td>
                        </tr>
                    `;
                });
            }

            function renderDrivers(drivers) {
                const tbody = document.getElementById('driver-list');
                tbody.innerHTML = '';
                Object.entries(drivers).forEach(([id, status]) => {
                    tbody.innerHTML += `
                        <tr>
                            <td><b>${id}번 기사님</b></td>
                            <td>${status}</td>
                        </tr>
                    `;
                });
            }
        </script>
    </body>
    </html>
    """

# 기사님 모바일 웹 페이지
@app.get("/driver", response_class=HTMLResponse)
async def get_driver_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>목포 퀵 - 기사님용</title>
        <style>
            body { font-family: 'Noto Sans KR', sans-serif; margin: 0; padding: 15px; background-color: #f8f9fa; }
            .header { background: #343a40; color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; text-align: center; }
            .driver-select { font-size: 16px; padding: 8px; width: 100%; border-radius: 5px; margin-top: 8px; }
            .order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-left: 5px solid #007bff; }
            .order-card.accepted { border-left-color: #28a745; background-color: #f1f9f3; }
            .location { font-size: 18px; font-weight: bold; color: #212529; margin: 5px 0; }
            .fee { font-size: 20px; font-weight: bold; color: #d9534f; text-align: right; margin-top: 10px; }
            .btn { width: 100%; padding: 15px; font-size: 18px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; margin-top: 10px; }
            .btn-accept { background: #28a745; color: white; }
            .btn-complete { background: #17a2b8; color: white; }
            .btn-disabled { background: #ccc; color: #666; }
        </style>
    </head>
    <body>
        <div class="header">
            <h2 style="margin:0;">🛵 목포 퀵 기사 앱</h2>
            <select id="driverId" class="driver-select" onchange="onDriverChange()">
                <option value="1">1번 기사님</option>
                <option value="2">2번 기사님</option>
                <option value="3">3번 기사님</option>
                <option value="4">4번 기사님</option>
                <option value="5">5번 기사님</option>
            </select>
        </div>

        <div id="order-container">
            <p style="text-align: center; color: #6c757d;">대기 중인 오더가 없습니다.</p>
        </div>

        <script>
            const ws = new WebSocket(`wss://${location.host}/ws`);
            let currentOrders = {};

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'INIT' || data.type === 'UPDATE') {
                    currentOrders = data.orders;
                    render();
                }
            };

            function onDriverChange() {
                render();
            }

            function render() {
                const myId = parseInt(document.getElementById('driverId').value);
                const container = document.getElementById('order-container');
                container.innerHTML = '';

                const ordersArray = Object.values(currentOrders).reverse();

                if (ordersArray.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #6c757d;">현재 등록된 오더가 없습니다.</p>';
                    return;
                }

                ordersArray.forEach(o => {
                    // 완료된 오더는 표시 안 함
                    if (o.status === '배달완료') return;

                    const isMine = o.driver_id === myId;
                    const isWaiting = o.status === '접수대기';

                    let buttonHtml = '';
                    if (isWaiting) {
                        buttonHtml = `<button class="btn btn-accept" onclick="acceptOrder(${o.id})">오더 수락하기</button>`;
                    } else if (isMine) {
                        buttonHtml = `<button class="btn btn-complete" onclick="completeOrder(${o.id})">배달 완료 처리</button>`;
                    } else {
                        buttonHtml = `<button class="btn btn-disabled" disabled>${o.driver_id}번 기사 수행 중</button>`;
                    }

                    container.innerHTML += `
                        <div class="order-card ${isMine ? 'accepted' : ''}">
                            <div style="font-size:12px; color:#6c757d;">오더 번호: #${o.id}</div>
                            <div class="location">🛫 출발: ${o.pickup}</div>
                            <div class="location">🛬 도착: ${o.destination}</div>
                            <div class="fee">${o.fee.toLocaleString()}원</div>
                            ${buttonHtml}
                        </div>
                    `;
                });
            }

            async function acceptOrder(orderId) {
                const driverId = parseInt(document.getElementById('driverId').value);
                await fetch(`/api/orders/${orderId}/accept?driver_id=${driverId}`, { method: 'POST' });
            }

            async function completeOrder(orderId) {
                const driverId = parseInt(document.getElementById('driverId').value);
                await fetch(`/api/orders/${orderId}/complete?driver_id=${driverId}`, { method: 'POST' });
            }
        </script>
    </body>
    </html>
    """

# ==========================================
# 3. API 및 웹소켓 백엔드 동작 로직
# ==========================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await websocket.send_json({"type": "INIT", "orders": orders_db, "drivers": drivers_status})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/orders")
async def create_order(order: OrderCreate):
    global order_counter
    new_order = {
        "id": order_counter,
        "pickup": order.pickup,
        "destination": order.destination,
        "fee": order.fee,
        "status": "접수대기",
        "driver_id": None
    }
    orders_db[order_counter] = new_order
    order_counter += 1
    await manager.broadcast({"type": "UPDATE", "orders": orders_db, "drivers": drivers_status})
    return {"status": "ok"}

@app.post("/api/orders/{order_id}/accept")
async def accept_order(order_id: int, driver_id: int):
    if order_id in orders_db and orders_db[order_id]["status"] == "접수대기":
        orders_db[order_id]["status"] = "배차완료"
        orders_db[order_id]["driver_id"] = driver_id
        drivers_status[driver_id] = "운행중"
        await manager.broadcast({"type": "UPDATE", "orders": orders_db, "drivers": drivers_status})
        return {"status": "ok"}
    return {"status": "fail"}

@app.post("/api/orders/{order_id}/complete")
async def complete_order(order_id: int, driver_id: int):
    if order_id in orders_db and orders_db[order_id]["driver_id"] == driver_id:
        orders_db[order_id]["status"] = "배달완료"
        drivers_status[driver_id] = "대기중"
        await manager.broadcast({"type": "UPDATE", "orders": orders_db, "drivers": drivers_status})
        return {"status": "ok"}
    return {"status": "fail"}
