from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime

app = FastAPI(title="Quick Call System")
DB_NAME = "quick_call.db"
FEE_RATE = 0.10  # 수수료율 10%

# --- DB 초기화 ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # 기사 테이블 (ID, 이름, 충전 잔액)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            balance INTEGER DEFAULT 0
        )
    ''')
    # 오더 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            price INTEGER NOT NULL,
            fee INTEGER NOT NULL,
            status TEXT DEFAULT 'WAITING',
            driver_id INTEGER,
            created_at TEXT
        )
    ''')
    # 샘플 기사 등록 (최초 1회)
    cursor.execute("SELECT COUNT(*) FROM drivers")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO drivers (name, balance) VALUES (?, ?)", [
            ("김기사", 50000),
            ("이기사", 30000),
            ("박기사", 20000)
        ])
    conn.commit()
    conn.close()

init_db()

# --- API 모델 ---
class OrderCreate(BaseModel):
    origin: str
    destination: str
    price: int

class OrderAccept(BaseModel):
    driver_id: int

# --- API 엔드포인트 ---
@app.post("/api/orders")
def create_order(order: OrderCreate):
    fee = int(order.price * FEE_RATE)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (origin, destination, price, fee, created_at) VALUES (?, ?, ?, ?, ?)",
        (order.origin, order.destination, order.price, fee, now)
    )
    conn.commit()
    conn.close()
    return {"message": "오더가 등록되었습니다."}

@app.post("/api/orders/{order_id}/accept")
def accept_order(order_id: int, req: OrderAccept):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT price, fee, status FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="오더 없음")
    if order[2] != 'WAITING':
        conn.close()
        raise HTTPException(status_code=400, detail="이미 배차된 오더입니다.")
        
    cursor.execute("SELECT balance FROM drivers WHERE id = ?", (req.driver_id,))
    driver = cursor.fetchone()
    if not driver:
        conn.close()
        raise HTTPException(status_code=404, detail="기사 없음")
        
    fee = order[1]
    if driver[0] < fee:
        conn.close()
        raise HTTPException(status_code=400, detail="충전금이 부족합니다.")
        
    cursor.execute("UPDATE drivers SET balance = balance - ? WHERE id = ?", (fee, req.driver_id))
    cursor.execute("UPDATE orders SET status = 'ACCEPTED', driver_id = ? WHERE id = ?", (req.driver_id, order_id))
    conn.commit()
    conn.close()
    return {"message": "배차 성공"}

@app.post("/api/orders/{order_id}/complete")
def complete_order(order_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'COMPLETED' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return {"message": "완료 처리되었습니다."}

@app.get("/api/dashboard")
def get_dashboard():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 전체 오더 목록
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cursor.fetchall()
    
    # 오늘 날짜
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 기사별 하루 통계 (오늘날짜 기준: 수락 건수, 완료 건수, 총 운임, 차감 수수료, 실수령액)
    cursor.execute('''
        SELECT 
            d.id, 
            d.name, 
            d.balance,
            COUNT(CASE WHEN o.driver_id = d.id AND o.created_at LIKE ? THEN 1 END) as today_accept_count,
            COUNT(CASE WHEN o.driver_id = d.id AND o.status = 'COMPLETED' AND o.created_at LIKE ? THEN 1 END) as today_complete_count,
            COALESCE(SUM(CASE WHEN o.driver_id = d.id AND o.status = 'COMPLETED' AND o.created_at LIKE ? THEN o.price ELSE 0 END), 0) as today_total_price,
            COALESCE(SUM(CASE WHEN o.driver_id = d.id AND o.created_at LIKE ? THEN o.fee ELSE 0 END), 0) as today_total_fee
        FROM drivers d
        LEFT JOIN orders o ON d.id = o.driver_id
        GROUP BY d.id
    ''', (f"{today}%", f"{today}%", f"{today}%", f"{today}%"))
    
    drivers = cursor.fetchall()
    conn.close()
    return {"orders": orders, "drivers": drivers, "today": today}

# --- 웹 화면 (UI) ---
@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>통합콜 관리자</title><meta charset="utf-8">
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f4f6f8; }
        .card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: center; }
        th { background: #333; color: white; }
        .highlight { font-weight: bold; color: #007bff; }
        .success { font-weight: bold; color: #28a745; }
    </style>
    </head>
    <body>
        <h2>📦 통합콜 관리자 대시보드</h2>
        <div class="card">
            <h3>신규 오더 띄우기</h3>
            출발지: <input id="orig" type="text"> 
            도착지: <input id="dest" type="text"> 
            운임: <input id="price" type="number">
            <button onclick="addOrder()">오더 등록</button>
        </div>
        
        <div class="card">
            <h3>📊 오늘 기사별 일일 정산 현황 (<span id="todayDate"></span>)</h3>
            <table id="driverTable">
                <tr>
                    <th>ID</th>
                    <th>기사명</th>
                    <th>충전금 잔액</th>
                    <th>오늘 수락 건수</th>
                    <th>오늘 완료 건수</th>
                    <th>오늘 총 운임</th>
                    <th>차감 수수료(10%)</th>
                    <th>기사 실 수령액</th>
                </tr>
            </table>
        </div>

        <div class="card">
            <h3>전체 오더 리스트</h3>
            <table id="orderTable"><tr><th>ID</th><th>출발지</th><th>도착지</th><th>운임</th><th>수수료</th><th>상태</th><th>수락 기사 ID</th><th>시간</th></tr></table>
        </div>

        <script>
            async function loadData() {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                
                document.getElementById('todayDate').innerText = data.today;
                
                // 기사별 정산 표 갱신
                let dHtml = `<tr>
                    <th>ID</th>
                    <th>기사명</th>
                    <th>충전금 잔액</th>
                    <th>오늘 수락</th>
                    <th>오늘 완료</th>
                    <th>오늘 총 운임</th>
                    <th>차감 수수료(10%)</th>
                    <th>기사 실 수령액</th>
                </tr>`;
                
                data.drivers.forEach(d => {
                    const id = d[0];
                    const name = d[1];
                    const balance = d[2];
                    const acceptCount = d[3];
                    const completeCount = d[4];
                    const totalPrice = d[5];
                    const totalFee = d[6];
                    const netPay = totalPrice - totalFee; // 실 수령액 = 총운임 - 차감수수료

                    dHtml += `<tr>
                        <td>${id}</td>
                        <td><b>${name}</b></td>
                        <td>${balance.toLocaleString()}원</td>
                        <td class="highlight">${acceptCount}건</td>
                        <td class="success">${completeCount}건</td>
                        <td>${totalPrice.toLocaleString()}원</td>
                        <td>${totalFee.toLocaleString()}원</td>
                        <td class="success"><b>${netPay.toLocaleString()}원</b></td>
                    </tr>`;
                });
                document.getElementById('driverTable').innerHTML = dHtml;

                // 오더 리스트 갱신
                let oHtml = '<tr><th>ID</th><th>출발지</th><th>도착지</th><th>운임</th><th>수수료</th><th>상태</th><th>수락 기사 ID</th><th>시간</th></tr>';
                data.orders.forEach(o => {
                    oHtml += `<tr><td>${o[0]}</td><td>${o[1]}</td><td>${o[2]}</td><td>${o[3].toLocaleString()}원</td><td>${o[4].toLocaleString()}원</td><td><b>${o[5]}</b></td><td>${o[6] || '-'}</td><td>${o[7]}</td></tr>`;
                });
                document.getElementById('orderTable').innerHTML = oHtml;
            }

            async function addOrder() {
                const origin = document.getElementById('orig').value;
                const destination = document.getElementById('dest').value;
                const price = parseInt(document.getElementById('price').value);

                if(!origin || !destination || !price) {
                    alert("출발지, 도착지, 운임을 모두 입력해주세요.");
                    return;
                }

                const res = await fetch('/api/orders', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ origin, destination, price })
                });

                if(res.ok) {
                    document.getElementById('orig').value = '';
                    document.getElementById('dest').value = '';
                    document.getElementById('price').value = '';
                    loadData();
                } else {
                    alert("오더 등록에 실패했습니다.");
                }
            }

            setInterval(loadData, 3000);
            loadData();
        </script>
    </body>
    </html>
    """

@app.get("/driver", response_class=HTMLResponse)
def driver_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>기사님 전용 앱</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: sans-serif; padding: 15px; background: #eef2f5; margin: 0; }
            .order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
            .btn { background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 5px; width: 100%; font-size: 16px; font-weight: bold; cursor: pointer; }
            .btn-complete { background: #28a745; margin-top: 5px; }
            .price { color: #d9534f; font-weight: bold; font-size: 18px; }
        </style>
    </head>
    <body>
        <h2>🛵 기사님 오더 창</h2>
        <div style="margin-bottom: 15px;">
            내 기사 ID 입력: <input id="driverId" type="number" value="1" style="width: 50px;">
        </div>
        <hr>
        <div id="list"></div>

        <script>
            async function loadOrders() {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                const myId = parseInt(document.getElementById('driverId').value);
                let html = '';

                data.orders.forEach(o => {
                    if(o[5] === 'WAITING') {
                        html += `
                        <div class="order-card">
                            <div><b>[대기중]</b> ${o[1]} ➔ ${o[2]}</div>
                            <div class="price">운임: ${o[3].toLocaleString()}원 (수수료: ${o[4].toLocaleString()}원)</div>
                            <button class="btn" style="margin-top:8px;" onclick="accept(${o[0]})">오더 수락하기</button>
                        </div>`;
                    } else if(o[5] === 'ACCEPTED' && o[6] === myId) {
                        html += `
                        <div class="order-card" style="border: 2px solid #007bff;">
                            <div><b>[운행중]</b> ${o[1]} ➔ ${o[2]}</div>
                            <div class="price">운임: ${o[3].toLocaleString()}원</div>
                            <button class="btn btn-complete" onclick="complete(${o[0]})">운행 완료하기</button>
                        </div>`;
                    }
                });
                document.getElementById('list').innerHTML = html || '<p>현재 잡을 수 있는 오더가 없습니다.</p>';
            }

            async function accept(orderId) {
                const driverId = document.getElementById('driverId').value;
                const res = await fetch(`/api/orders/${orderId}/accept`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ driver_id: parseInt(driverId) })
                });
                const result = await res.json();
                if(!res.ok) alert(result.detail);
                loadOrders();
            }

            async function complete(orderId) {
                await fetch(`/api/orders/${orderId}/complete`, { method: 'POST' });
                loadOrders();
            }

            setInterval(loadOrders, 2000);
            loadOrders();
        </script>
    </body>
    </html>
    """