from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime

app = FastAPI()

FEE_RATE = 0.15  # 수수료율 15%

orders_db: Dict[int, dict] = {}

# 기사님 1번부터 100번까지 기본이름 생성
drivers_db: Dict[int, str] = {i: f"{i}번 기사" for i in range(1, 101)}

order_counter = 1

class OrderCreate(BaseModel):
    pickup: str
    destination: str
    fee: int
    content: Optional[str] = ""

class OrderUpdate(BaseModel):
    pickup: str
    destination: str
    fee: int
    content: Optional[str] = ""

class DriverNameUpdate(BaseModel):
    driver_id: int
    name: str

@app.get("/")
async def root():
    return RedirectResponse(url="/driver")

# --- API 엔드포인트 ---
@app.get("/api/orders")
async def get_orders(date: str = None):
    target_date = date if date else datetime.now().strftime("%Y-%m-%d")
    target_month = target_date[:7] # YYYY-MM

    daily_settlement = {d_id: {"name": d_name, "count": 0, "fare": 0, "fee": 0, "net": 0} for d_id, d_name in drivers_db.items()}
    monthly_settlement = {d_id: {"name": d_name, "count": 0, "fare": 0, "fee": 0, "net": 0} for d_id, d_name in drivers_db.items()}

    filtered_orders = {}

    for o_id, o in orders_db.items():
        o_date = o.get("date", "")
        o_month = o_date[:7] if o_date else ""

        if o_date == target_date:
            filtered_orders[o_id] = o

        if o["status"] == "배달완료" and o["driver_id"] in drivers_db:
            d_id = o["driver_id"]
            fare = o["fee"]
            fee = int(fare * FEE_RATE)
            net = fare - fee

            # 일일 집계
            if o_date == target_date:
                daily_settlement[d_id]["count"] += 1
                daily_settlement[d_id]["fare"] += fare
                daily_settlement[d_id]["fee"] += fee
                daily_settlement[d_id]["net"] += net

            # 월별 집계
            if o_month == target_month:
                monthly_settlement[d_id]["count"] += 1
                monthly_settlement[d_id]["fare"] += fare
                monthly_settlement[d_id]["fee"] += fee
                monthly_settlement[d_id]["net"] += net

    return {
        "orders": filtered_orders,
        "daily_settlement": daily_settlement,
        "monthly_settlement": monthly_settlement,
        "drivers": drivers_db,
        "target_date": target_date,
        "target_month": target_month
    }

@app.post("/api/drivers/name")
async def update_driver_name(data: DriverNameUpdate):
    if data.driver_id in drivers_db:
        drivers_db[data.driver_id] = data.name.strip() if data.name.strip() else f"{data.driver_id}번 기사"
        return {"status": "ok", "name": drivers_db[data.driver_id]}
    raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")

@app.post("/api/orders")
async def create_order(order: OrderCreate):
    global order_counter
    today_str = datetime.now().strftime("%Y-%m-%d")
    new_order = {
        "id": order_counter,
        "pickup": order.pickup,
        "destination": order.destination,
        "fee": order.fee,
        "content": order.content,
        "status": "접수대기",
        "driver_id": None,
        "date": today_str
    }
    orders_db[order_counter] = new_order
    order_counter += 1
    return {"status": "ok"}

@app.put("/api/orders/{order_id}")
async def update_order(order_id: int, order: OrderUpdate):
    if order_id in orders_db:
        orders_db[order_id]["pickup"] = order.pickup
        orders_db[order_id]["destination"] = order.destination
        orders_db[order_id]["fee"] = order.fee
        orders_db[order_id]["content"] = order.content
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="오더를 찾을 수 없습니다.")

@app.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: int):
    if order_id in orders_db:
        orders_db[order_id]["status"] = "취소됨"
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="오더를 찾을 수 없습니다.")

@app.post("/api/orders/{order_id}/accept")
async def accept_order(order_id: int, driver_id: int):
    if order_id in orders_db and orders_db[order_id]["status"] == "접수대기":
        orders_db[order_id]["status"] = "배차완료"
        orders_db[order_id]["driver_id"] = driver_id
        return {"status": "ok"}
    raise HTTPException(status_code=400, detail="이미 배차되었거나 취소/완료된 오더입니다.")

@app.post("/api/orders/{order_id}/complete")
async def complete_order(order_id: int, driver_id: int):
    if order_id in orders_db and orders_db[order_id]["driver_id"] == driver_id and orders_db[order_id]["status"] == "배차완료":
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
            .status-waiting { color: #007bff; font-weight: bold; }
            .status-ing { color: #ff9800; font-weight: bold; }
            .status-done { color: #28a745; font-weight: bold; }
            .status-canceled { color: #dc3545; font-weight: bold; text-decoration: line-through; }
            .date-picker { font-size: 16px; padding: 8px; margin-bottom: 5px; width: 100%; box-sizing: border-box; }
            .btn-sm { padding: 5px 10px; font-size: 12px; font-weight: bold; border-radius: 4px; border: none; cursor: pointer; margin: 2px; }
            .btn-edit { background: #ffc107; color: #333; }
            .btn-cancel { background: #dc3545; color: white; }
            .table-scroll { max-height: 400px; overflow-y: auto; }
        </style>
    </head>
    <body>
        <h1>📦 목포 퀵 관제 센터</h1>
        
        <div class="card">
            <h2>📅 날짜 선택 (자체 달력)</h2>
            <input type="date" id="searchDate" class="date-picker" onchange="fetchOrders()">
        </div>

        <div class="card">
            <h2>신규 오더 접수</h2>
            <div class="form-group"><label>출발지</label><input type="text" id="pickup" placeholder="예: 평화광장"></div>
            <div class="form-group"><label>도착지</label><input type="text" id="destination" placeholder="예: 목포역"></div>
            <div class="form-group"><label>오더 내용 (물품명)</label><input type="text" id="content" placeholder="예: 서류 봉투, 꽃바구니, 소형 박스 등"></div>
            <div class="form-group"><label>요금 (원)</label><input type="number" id="fee" placeholder="예: 8000"></div>
            <button onclick="createOrder()">오더 등록하기</button>
        </div>

        <div class="card">
            <h2>📊 <span id="daily-title">일일</span> 정산 현황 (수수료 15%)</h2>
            <div class="table-scroll">
                <table>
                    <thead>
                        <tr><th>ID</th><th>기사명</th><th>완료 건수</th><th>총 운임</th><th>수수료 (15%)</th><th>기사 실 수령액</th></tr>
                    </thead>
                    <tbody id="daily-list"></tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <h2>🗓️ <span id="monthly-title">월간</span> 정산 현황 (수수료 15%)</h2>
            <div class="table-scroll">
                <table>
                    <thead>
                        <tr><th>ID</th><th>기사명</th><th>완료 건수</th><th>총 운임</th><th>수수료 (15%)</th><th>기사 실 수령액</th></tr>
                    </thead>
                    <tbody id="monthly-list"></tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <h2>📜 해당 날짜 오더 및 관제 관리</h2>
            <table>
                <thead>
                    <tr><th>번호</th><th>출발지</th><th>도착지</th><th>오더 내용</th><th>총 요금</th><th>수수료(15%)</th><th>실수령액</th><th>상태</th><th>수행 기사</th><th>관리</th></tr>
                </thead>
                <tbody id="order-list"></tbody>
            </table>
        </div>

        <script>
            document.getElementById('searchDate').value = new Date().toISOString().substring(0, 10);
            let driversDict = {};

            async function fetchOrders() {
                const dateVal = document.getElementById('searchDate').value;
                try {
                    const res = await fetch(`/api/orders?date=${dateVal}`);
                    const data = await res.json();
                    
                    driversDict = data.drivers;
                    document.getElementById('daily-title').innerText = `${data.target_date} 일일`;
                    document.getElementById('monthly-title').innerText = `${data.target_month} 월간`;

                    renderSettlement('daily-list', data.daily_settlement);
                    renderSettlement('monthly-list', data.monthly_settlement);
                    renderOrders(data.orders);
                } catch(e) {}
            }

            async function createOrder() {
                const pickup = document.getElementById('pickup').value;
                const destination = document.getElementById('destination').value;
                const content = document.getElementById('content').value;
                const fee = parseInt(document.getElementById('fee').value);

                if (!pickup || !destination || !fee) {
                    alert('출발지, 도착지, 요금을 입력해 주세요.');
                    return;
                }

                const res = await fetch('/api/orders', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pickup, destination, fee, content })
                });

                if(res.ok) {
                    document.getElementById('pickup').value = '';
                    document.getElementById('destination').value = '';
                    document.getElementById('content').value = '';
                    document.getElementById('fee').value = '';
                    fetchOrders();
                }
            }

            async function editOrder(id, curPickup, curDest, curContent, curFee) {
                const newPickup = prompt("수정할 출발지:", curPickup);
                if (newPickup === null) return;
                const newDest = prompt("수정할 도착지:", curDest);
                if (newDest === null) return;
                const newContent = prompt("수정할 오더 내용(물품명):", curContent || "");
                if (newContent === null) return;
                const newFeeStr = prompt("수정할 요금(원):", curFee);
                if (newFeeStr === null) return;

                const newFee = parseInt(newFeeStr);

                const res = await fetch(`/api/orders/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pickup: newPickup, destination: newDest, content: newContent, fee: newFee })
                });

                if(res.ok) {
                    alert("오더가 수정되었습니다. 기사 앱에도 변경 내용이 반영됩니다.");
                    fetchOrders();
                } else {
                    alert("수정 실패");
                }
            }

            async function cancelOrder(id) {
                if(confirm(`노선 번호 #${id} 오더를 정말 취소하시겠습니까? 기사님 앱에서도 취소 처리됩니다.`)) {
                    const res = await fetch(`/api/orders/${id}/cancel`, { method: 'POST' });
                    if(res.ok) {
                        alert("오더가 취소되었습니다.");
                        fetchOrders();
                    } else {
                        alert("취소 실패");
                    }
                }
            }

            function renderSettlement(elementId, settlement) {
                const tbody = document.getElementById(elementId);
                tbody.innerHTML = '';
                Object.entries(settlement).forEach(([id, s]) => {
                    if (s.count > 0) {
                        tbody.innerHTML += `
                            <tr>
                                <td>${id}번</td>
                                <td><b>${s.name}</b></td>
                                <td>${s.count}건</td>
                                <td>${s.fare.toLocaleString()}원</td>
                                <td>${s.fee.toLocaleString()}원</td>
                                <td class="highlight">${s.net.toLocaleString()}원</td>
                            </tr>
                        `;
                    }
                });

                if (tbody.innerHTML === '') {
                    tbody.innerHTML = '<tr><td colspan="6" style="color:#888;">완료된 정산 내역이 없습니다.</td></tr>';
                }
            }

            function renderOrders(orders) {
                const tbody = document.getElementById('order-list');
                tbody.innerHTML = '';
                Object.values(orders).reverse().forEach(o => {
                    const fee15 = Math.floor(o.fee * 0.15);
                    const net = o.fee - fee15;
                    const contentText = o.content ? o.content : "-";
                    
                    let statusClass = "status-waiting";
                    let driverInfo = "-";

                    if (o.status === "배차완료") {
                        statusClass = "status-ing";
                        const dName = driversDict[o.driver_id] || "";
                        driverInfo = `<span style="color:#d9534f; font-weight:bold;">🛵 ${o.driver_id}번 ${dName} 수행중</span>`;
                    } else if (o.status === "배달완료") {
                        statusClass = "status-done";
                        const dName = driversDict[o.driver_id] || "";
                        driverInfo = `<b>${o.driver_id}번 ${dName} (완료)</b>`;
                    } else if (o.status === "취소됨") {
                        statusClass = "status-canceled";
                        driverInfo = `<span style="color:#888;">(취소됨)</span>`;
                    }

                    let actionBtns = '';
                    if (o.status !== '배달완료' && o.status !== '취소됨') {
                        actionBtns = `
                            <button class="btn-sm btn-edit" onclick="editOrder(${o.id}, '${o.pickup}', '${o.destination}', '${o.content || ''}', ${o.fee})">수정</button>
                            <button class="btn-sm btn-cancel" onclick="cancelOrder(${o.id})">취소</button>
                        `;
                    } else {
                        actionBtns = `-`;
                    }

                    tbody.innerHTML += `
                        <tr>
                            <td>${o.id}</td>
                            <td>${o.pickup}</td>
                            <td>${o.destination}</td>
                            <td><b>${contentText}</b></td>
                            <td>${o.fee.toLocaleString()}원</td>
                            <td>${fee15.toLocaleString()}원</td>
                            <td class="highlight">${net.toLocaleString()}원</td>
                            <td class="${statusClass}">${o.status}</td>
                            <td>${driverInfo}</td>
                            <td>${actionBtns}</td>
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
            .driver-select { font-size: 16px; padding: 8px; width: 100%; border-radius: 5px; margin-top: 8px; box-sizing: border-box; }
            .driver-input { font-size: 16px; padding: 8px; width: 100%; border-radius: 5px; margin-top: 8px; box-sizing: border-box; border: 1px solid #ccc; }
            .lock-btn { margin-top: 8px; background: #28a745; color: white; border: none; padding: 10px; border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%; font-size: 15px; }
            .unlock-btn { margin-top: 8px; background: #dc3545; color: white; border: none; padding: 6px 10px; border-radius: 5px; font-size: 12px; cursor: pointer; }
            .date-card { background: white; padding: 12px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            .date-picker { font-size: 16px; padding: 8px; width: 100%; box-sizing: border-box; border-radius: 5px; border: 1px solid #ccc; }
            .summary-card { background: #007bff; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: center; }
            .summary-card h3 { margin: 0 0 10px 0; font-size: 16px; }
            .summary-card .amount { font-size: 24px; font-weight: bold; }
            .order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-left: 5px solid #007bff; }
            .order-card.accepted { border-left-color: #28a745; background-color: #f1f9f3; }
            .order-card.completed { border-left-color: #6c757d; background-color: #e9ecef; }
            .order-card.canceled { border-left-color: #dc3545; background-color: #f8d7da; }
            .location { font-size: 18px; font-weight: bold; color: #212529; margin: 5px 0; }
            .content-box { background: #eef2f5; padding: 8px 12px; border-radius: 5px; font-size: 15px; color: #333; margin: 8px 0; font-weight: bold; }
            .fee { font-size: 18px; font-weight: bold; color: #d9534f; text-align: right; margin-top: 10px; }
            .net-fee { font-size: 16px; color: #28a745; text-align: right; font-weight: bold; }
            .btn { width: 100%; padding: 15px; font-size: 18px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; margin-top: 10px; }
            .btn-accept { background: #28a745; color: white; }
            .btn-complete { background: #17a2b8; color: white; }
            .btn-disabled { background: #ccc; color: #666; }
            .btn-canceled { background: #dc3545; color: white; }
            .tab-btn { padding: 10px; width: 48%; margin-bottom: 10px; font-weight:bold; border-radius: 5px; border: 1px solid #007bff; background: white; color: #007bff; }
            .tab-btn.active { background: #007bff; color: white; }
        </style>
    </head>
    <body>
        <div class="header">
            <h2 style="margin:0;">🛵 목포 퀵 기사 앱</h2>
            <div id="account-area">
                <select id="driverId" class="driver-select"></select>
                <input type="text" id="driverNameInput" class="driver-input" placeholder="기사님 이름 입력 (예: 홍길동)">
                <button class="lock-btn" onclick="lockAccount()">🔒 계정 고정 및 이름 등록</button>
            </div>
            <div id="locked-area" style="display:none; margin-top:8px;">
                <span id="locked-driver-name" style="font-size:18px; font-weight:bold; color:#ffc107;"></span>
                <br>
                <button class="unlock-btn" onclick="unlockAccount()">🔒 계정 변경 (잠금 해제)</button>
            </div>
        </div>

        <div class="date-card">
            <label style="font-weight:bold; font-size:14px; display:block; margin-bottom:5px;">📅 날짜 선택 (과거 내역 조회)</label>
            <input type="date" id="searchDate" class="date-picker" onchange="fetchOrders()">
        </div>

        <div class="summary-card">
            <h3>💰 선택 날짜 완료 실수령액 (수수료 15% 차감)</h3>
            <div class="amount" id="today-net">0 원</div>
            <div style="margin-top:5px; font-size:12px;" id="today-summary">0건 완료 / 총 운임 0원 (수수료 0원)</div>
        </div>

        <div>
            <button id="tab-waiting" class="tab-btn active" onclick="switchTab('waiting')">신규/운행중 오더</button>
            <button id="tab-done" class="tab-btn" onclick="switchTab('done')">수행 완료 내역</button>
        </div>

        <div id="order-container"></div>

        <script>
            document.getElementById('searchDate').value = new Date().toISOString().substring(0, 10);
            let currentTab = 'waiting';
            let currentDriverId = 1;
            let currentDriverName = "";

            function populateDriverSelect() {
                const select = document.getElementById('driverId');
                select.innerHTML = '';
                for (let i = 1; i <= 100; i++) {
                    const opt = document.createElement('option');
                    opt.value = i;
                    opt.innerText = `${i}번 기사 번호 선택`;
                    select.appendChild(opt);
                }
            }

            async function initAccount() {
                populateDriverSelect();
                const savedDriverId = localStorage.getItem('mokpo_driver_id');
                const savedDriverName = localStorage.getItem('mokpo_driver_name');

                if (savedDriverId) {
                    currentDriverId = parseInt(savedDriverId);
                    currentDriverName = savedDriverName || `${currentDriverId}번 기사`;

                    document.getElementById('account-area').style.display = 'none';
                    document.getElementById('locked-area').style.display = 'block';
                    document.getElementById('locked-driver-name').innerText = `👤 ${currentDriverId}번 [${currentDriverName}] 로그인됨`;

                    // 서버에 고정된 기사명 동기화
                    await fetch('/api/drivers/name', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ driver_id: currentDriverId, name: currentDriverName })
                    });
                } else {
                    document.getElementById('account-area').style.display = 'block';
                    document.getElementById('locked-area').style.display = 'none';
                    currentDriverId = parseInt(document.getElementById('driverId').value || 1);
                }
            }

            async function lockAccount() {
                const selId = parseInt(document.getElementById('driverId').value);
                const nameInput = document.getElementById('driverNameInput').value.trim();

                if (!nameInput) {
                    alert("기사님 성함 또는 이름을 입력해 주세요!");
                    return;
                }

                const res = await fetch('/api/drivers/name', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ driver_id: selId, name: nameInput })
                });

                if (res.ok) {
                    const data = await res.json();
                    localStorage.setItem('mokpo_driver_id', selId);
                    localStorage.setItem('mokpo_driver_name', data.name);
                    alert(`${selId}번 [${data.name}]님으로 계정이 고정되었습니다.`);
                    initAccount();
                    fetchOrders();
                }
            }

            function unlockAccount() {
                if(confirm("계정을 변경하시겠습니까?")) {
                    localStorage.removeItem('mokpo_driver_id');
                    localStorage.removeItem('mokpo_driver_name');
                    initAccount();
                    fetchOrders();
                }
            }

            function switchTab(tab) {
                currentTab = tab;
                document.getElementById('tab-waiting').classList.toggle('active', tab === 'waiting');
                document.getElementById('tab-done').classList.toggle('active', tab === 'done');
                fetchOrders();
            }

            async function fetchOrders() {
                const dateVal = document.getElementById('searchDate').value;
                try {
                    const res = await fetch(`/api/orders?date=${dateVal}`);
                    const data = await res.json();
                    render(data.orders, data.daily_settlement);
                } catch(e) {}
            }

            function render(currentOrders, dailySettlement) {
                const myId = currentDriverId;
                
                const myStat = dailySettlement[myId] || { count: 0, fare: 0, fee: 0, net: 0 };
                document.getElementById('today-net').innerText = `${myStat.net.toLocaleString()} 원`;
                document.getElementById('today-summary').innerText = `${myStat.count}건 완료 / 총 운임 ${myStat.fare.toLocaleString()}원 (수수료 ${myStat.fee.toLocaleString()}원)`;

                const container = document.getElementById('order-container');
                container.innerHTML = '';

                const ordersArray = Object.values(currentOrders).reverse();

                if (currentTab === 'waiting') {
                    const waitingOrders = ordersArray.filter(o => o.status !== '배달완료');
                    if (waitingOrders.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: #6c757d;">대기 중인 오더가 없습니다.</p>';
                        return;
                    }

                    waitingOrders.forEach(o => {
                        const isMine = o.driver_id === myId;
                        const isWaiting = o.status === '접수대기';
                        const isCanceled = o.status === '취소됨';

                        let buttonHtml = '';
                        let cardClass = '';

                        if (isCanceled) {
                            if (isMine || isWaiting) {
                                cardClass = 'canceled';
                                buttonHtml = `<button class="btn btn-canceled" disabled>🚫 관리자에 의해 취소된 오더입니다</button>`;
                            } else {
                                return;
                            }
                        } else if (isWaiting) {
                            buttonHtml = `<button class="btn btn-accept" onclick="acceptOrder(${o.id})">오더 수락하기</button>`;
                        } else if (isMine) {
                            cardClass = 'accepted';
                            buttonHtml = `<button class="btn btn-complete" onclick="completeOrder(${o.id})">배달 완료 처리</button>`;
                        } else {
                            buttonHtml = `<button class="btn btn-disabled" disabled>${o.driver_id}번 기사 수행 중</button>`;
                        }

                        const fee15 = Math.floor(o.fee * 0.15);
                        const netFare = o.fee - fee15;
                        const contentHtml = o.content ? `<div class="content-box">📦 내용: ${o.content}</div>` : '';

                        container.innerHTML += `
                            <div class="order-card ${cardClass}">
                                <div style="font-size:12px; color:#6c757d;">오더 번호: #${o.id} ${isCanceled ? '<b style="color:red;">[취소됨]</b>' : ''}</div>
                                <div class="location">🛫 출발: ${o.pickup}</div>
                                <div class="location">🛬 도착: ${o.destination}</div>
                                ${contentHtml}
                                <div class="fee">운임: ${o.fee.toLocaleString()}원</div>
                                <div class="net-fee">실수령액 (85%): ${netFare.toLocaleString()}원</div>
                                ${buttonHtml}
                            </div>
                        `;
                    });
                } else {
                    const myDoneOrders = ordersArray.filter(o => o.status === '배달완료' && o.driver_id === myId);
                    if (myDoneOrders.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: #6c757d;">선택한 날짜에 완료한 배달 내역이 없습니다.</p>';
                        return;
                    }

                    myDoneOrders.forEach(o => {
                        const fee15 = Math.floor(o.fee * 0.15);
                        const netFare = o.fee - fee15;
                        const contentHtml = o.content ? `<div class="content-box">📦 내용: ${o.content}</div>` : '';

                        container.innerHTML += `
                            <div class="order-card completed">
                                <div style="font-size:12px; color:#6c757d;">오더 번호: #${o.id} (완료)</div>
                                <div class="location">🛫 출발: ${o.pickup}</div>
                                <div class="location">🛬 도착: ${o.destination}</div>
                                ${contentHtml}
                                <div class="fee">총 운임: ${o.fee.toLocaleString()}원</div>
                                <div class="net-fee">정산 실수령액: ${netFare.toLocaleString()}원 (수수료 15% 차감)</div>
                            </div>
                        `;
                    });
                }
            }

            async function acceptOrder(orderId) {
                const driverId = currentDriverId;
                const res = await fetch(`/api/orders/${orderId}/accept?driver_id=${driverId}`, { method: 'POST' });
                if(!res.ok) {
                    const err = await res.json();
                    alert(err.detail || "수락할 수 없는 오더입니다.");
                }
                fetchOrders();
            }

            async function completeOrder(orderId) {
                const driverId = currentDriverId;
                const res = await fetch(`/api/orders/${orderId}/complete?driver_id=${driverId}`, { method: 'POST' });
                if(!res.ok) {
                    alert("취소되었거나 처리할 수 없는 오더입니다.");
                }
                fetchOrders();
            }

            initAccount();
            setInterval(fetchOrders, 2000);
            fetchOrders();
        </script>
    </body>
    </html>
    """
