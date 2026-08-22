from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

FEE_RATE = 0.15  # 수수료율 15%

# 데이터 저장 구조 (오더 및 기사 1~5번 데이터)
orders_db: Dict[int, dict] = {}
drivers_db: Dict[int, str] = {1: "김기사", 2: "이기사", 3: "박기사", 4: "최기사", 5: "정기사"}
order_counter = 1

class OrderCreate(BaseModel):
    pickup: str
    destination: str
    fee: int

@app.get("/")
async def root():
    return RedirectResponse(url="/driver")

# --- API 엔드포인트 ---
@app.get("/api/orders")
async def get_orders():
    # 기사별 정산 집계 계산
    settlement = {}
    for d_id, d_name in drivers_db.items():
        settlement[d_id] = {
            "name": d_name,
            "completed_count": 0,
            "total_fare": 0,
            "total_fee": 0,
            "net_pay": 0
        }
    
    for o in orders_db.values():
        if o["status"] == "배달완료" and o["driver_id"] in settlement:
            d_id = o["driver_id"]
            fare = o["fee"]
            fee = int(fare * FEE_RATE)
            settlement[d_id]["completed_count"] += 1
            settlement[d_id]["total_fare"] += fare
            settlement[d_id]["total_fee"] += fee
            settlement[d_id]["net_pay"] += (fare - fee)

    return {"orders": orders_db, "settlement": settlement}

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
    return {"status": "ok"}

@app.post("/api/orders/{order_id}/accept")
async def accept_order(order_id: int, driver_id: int):
    if order_id in orders_db and orders_db[order_id]["status"] == "접수대기":
        orders_db[order_id]["status"] = "배차완료"
        orders_db[order_id]["driver_id"] = driver_id
        return {"status": "ok"}
    raise HTTPException(status_code=400, detail="이미 배차되었거나 없는 오더입니다.")

@app.post("/api/orders/{order_id}/complete")
async def complete_order(order_id: int, driver_id: int):
    if order_id in orders_db and orders_db[order_id]["driver_id"] == driver_id:
        orders_db[order_id]["status"] = "배달완료"
        return {"status": "ok"}
    raise HTTPException(status_code=400, detail="처리 실패")

# --- PC 관리자 페이지 ---
@app.get("/admin", response_class=HTMLResponse)
async def get_admin_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>목포 퀵 관제 Center</title>
        <style>
            body { font-family: sans-serif; margin: 0; padding: 20px; background-color: #f4f6f9; }
            h1 { text-align: center; color: #333; }
            .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .form-group { margin-bottom: 12px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 5px; }
            button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 5px; font-size: 16px; font-weight: bold; cursor: pointer; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: center; }
            th { background-color: #333; color: white; }
            .highlight { color: #28a745; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>📦 목포 퀵 관제 센터</h1>
        
        <div class="card">
            <h2>신규 오더 접수</h2>
            <div class="form-group"><label>출발지</label><input type="text" id="pickup" placeholder="예: 평화광장"></div>
            <div class="form-group"><label>도착지</label><input type="text" id="destination" placeholder="예: 목포역"></div>
            <div class="form-group"><label>요금 (원)</label><input type="number" id="fee" placeholder="예: 8000"></div>
            <button onclick="createOrder()">오더 등록하기</button>
        </div>

        <div class="card">
            <h2>📊 기사별 일일 정산 현황</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>기사명</th>
                        <th>완료 건수</th>
                        <th>총 운임</th>
                        <th>수수료 (10%)</th>
                        <th>기사 실 수령액</th>
                    </tr>
                </thead>
                <tbody id="settlement-list"></tbody>
            </table>
        </div>

        <div class="card">
            <h2>실시간 오더 현황</h2>
            <table>
                <thead>
                    <tr><th>번호</th><th>출발지</th><th>도착지</th><th>요금</th><th>상태</th><th>담당 기사</th></tr>
                </thead>
                <tbody id="order-list"></tbody>
            </table>
        </div>

        <script>
            async function fetchOrders() {
                try {
                    const res = await fetch('/api/orders');
                    const data = await res.json();
                    renderOrders(data.orders);
                    renderSettlement(data.settlement);
                } catch(e) {}
            }

            async function createOrder() {
                const pickup = document.getElementById('pickup').value;
                const destination = document.getElementById('destination').value;
                const fee = parseInt(document.getElementById('fee').value);

                if (!pickup || !destination || !fee) {
                    alert('모든 항목을 입력해 주세요.');
                    return;
                }

                const res = await fetch('/api/orders', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pickup, destination, fee })
                });

                if(res.ok) {
                    document.getElementById('pickup').value = '';
                    document.getElementById('destination').value = '';
                    document.getElementById('fee').value = '';
                    fetchOrders();
                } else {
                    alert('오더 등록 실패');
                }
            }

            function renderSettlement(settlement) {
                const tbody = document.getElementById('settlement-list');
                tbody.innerHTML = '';
                Object.entries(settlement).forEach(([id, s]) => {
                    tbody.innerHTML += `
                        <tr>
                            <td>${id}번</td>
                            <td><b>${s.name}</b></td>
                            <td>${s.completed_count}건</td>
                            <td>${s.total_fare.toLocaleString()}원</td>
                            <td>${s.total_fee.toLocaleString()}원</td>
                            <td class="highlight">${s.net_pay.toLocaleString()}원</td>
                        </tr>
                    `;
                });
            }

            function renderOrders(orders) {
                const tbody = document.getElementById('order-list');
                tbody.innerHTML = '';
                Object.values(orders).reverse().forEach(o => {
                    tbody.innerHTML += `
                        <tr>
                            <td>${o.id}</td>
                            <td>${o.pickup}</td>
                            <td>${o.destination}</td>
                            <td>${o.fee.toLocaleString()}원</td>
                            <td><b>${o.status}</b></td>
                            <td>${o.driver_id ? o.driver_id + '번 기사' : '-'}</td>
                        </tr>
                    `;
                });
            }

            setInterval(fetchOrders, 2000);
            fetchOrders();
        </script>
    </body>
    </html>
    """

# --- 기사님 모바일 페이지 ---
@app.get("/driver", response_class=HTMLResponse)
async def get_driver_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>목포 퀵 - 기사님용</title>
        <style>
            body { font-family: sans-serif; margin: 0; padding: 15px; background-color: #f8f9fa; }
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
            <select id="driverId" class="driver-select" onchange="fetchOrders()">
                <option value="1">1번 김기사님</option>
                <option value="2">2번 이기사님</option>
                <option value="3">3번 박기사님</option>
                <option value="4">4번 최기사님</option>
                <option value="5">5번 정기사님</option>
            </select>
        </div>

        <div id="order-container">
            <p style="text-align: center; color: #6c757d;">대기 중인 오더가 없습니다.</p>
        </div>

        <script>
            async function fetchOrders() {
                try {
                    const res = await fetch('/api/orders');
                    const data = await res.json();
                    render(data.orders);
                } catch(e) {}
            }

            function render(currentOrders) {
                const myId = parseInt(document.getElementById('driverId').value);
                const container = document.getElementById('order-container');
                container.innerHTML = '';

                const ordersArray = Object.values(currentOrders).reverse();

                if (ordersArray.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #6c757d;">현재 등록된 오더가 없습니다.</p>';
                    return;
                }

                ordersArray.forEach(o => {
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
                fetchOrders();
            }

            async function completeOrder(orderId) {
                const driverId = parseInt(document.getElementById('driverId').value);
                await fetch(`/api/orders/${orderId}/complete?driver_id=${driverId}`, { method: 'POST' });
                fetchOrders();
            }

            setInterval(fetchOrders, 2000);
            fetchOrders();
        </script>
    </body>
    </html>
    """
