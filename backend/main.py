from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import hmac
import base64
import json
import os


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="EMS Bonus Calculator API",
    description="Backend API for EMS bonus calculation.",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",

        # Your Vercel website will be added here later
        "https://YOUR-VERCEL-APP.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SECURITY
# ============================================================

security = HTTPBearer()

SECRET_KEY = os.getenv(
    "EMS_BONUS_SECRET",
    "change-this-secret-key-for-production"
)


# ============================================================
# SIMPLE LOGIN DATABASE
# ============================================================
#
# You can change these accounts later.
#
# Username: admin
# Password: admin123
#
# Username: hr
# Password: hr123
#
# Username: manager
# Password: manager123
#
# ============================================================

USERS = {
    "admin": {
        "password": "admin123",
        "role": "Admin",
        "name": "EMS Administrator",
    },
    "hr": {
        "password": "hr123",
        "role": "HR",
        "name": "Human Resources",
    },
    "manager": {
        "password": "manager123",
        "role": "Manager",
        "name": "EMS Manager",
    },
}


# ============================================================
# PASSWORD / TOKEN HELPERS
# ============================================================

def create_token(username: str) -> str:
    """
    Creates a simple signed token.

    This is intentionally lightweight for the project.
    For a production deployment, use a proper JWT library.
    """

    payload = {
        "username": username,
        "exp": int(
            (datetime.utcnow() + timedelta(hours=12)).timestamp()
        ),
    }

    payload_string = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode()

    signature = hmac.new(
        SECRET_KEY.encode(),
        payload_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    return f"{payload_string}.{signature}"


def verify_token(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")

        if len(parts) != 2:
            raise ValueError("Invalid token")

        payload_string = parts[0]
        received_signature = parts[1]

        expected_signature = hmac.new(
            SECRET_KEY.encode(),
            payload_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            received_signature,
            expected_signature,
        ):
            raise ValueError("Invalid signature")

        payload = json.loads(
            base64.urlsafe_b64decode(
                payload_string.encode()
            ).decode()
        )

        if payload["exp"] < int(datetime.utcnow().timestamp()):
            raise ValueError("Token expired")

        return payload

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login session.",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    return verify_token(credentials.credentials)


# ============================================================
# BONUS RATES
# ============================================================

BONUS_RATES = {

    # --------------------------------------------------------
    # LABTECH
    # --------------------------------------------------------

    "captcha": 10000,

    "delivery_bonus": 5000,

    # Delivery also receives:
    # $5,000 per delivery + $5,000 delivery bonus
    "delivery_paycheck": 5000,


    # --------------------------------------------------------
    # FTO
    # --------------------------------------------------------

    "day_1_training": 55000,

    "day_2_training": 50000,

    "labtech_training": 30000,

    "refresher_training": 30000,


    # --------------------------------------------------------
    # RESCUE OFFICER
    # --------------------------------------------------------

    "unscripted_event": 15000,

    "scripted_event": 25000,


    # --------------------------------------------------------
    # HIGH COMMAND
    # --------------------------------------------------------

    "high_command_hour": 10000,


    # --------------------------------------------------------
    # MEDICAL / AMBULANCE
    # --------------------------------------------------------

    "day_ph1": 10000,
    "day_ph2": 10000,

    "late_ph1": 20000,
    "late_ph2": 20000,

    "night_ph1": 20000,
    "night_ph2": 20000,

    "day_on_calls": 10000,
    "late_on_calls": 20000,
    "night_on_calls": 20000,

    "standby": 10000,

    "ambulance_day": 10000,
    "ambulance_late": 20000,
    "ambulance_night": 20000,
}


# ============================================================
# MODELS
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class Person(BaseModel):
    name: str
    employee_id: str
    department: str


class LobbyLog(BaseModel):
    lobby: str
    on_duty: str
    off_duty: str
    date: Optional[str] = None


class ActivityCounts(BaseModel):
    captcha: int = 0
    deliveries: int = 0

    day_1_training: int = 0
    day_2_training: int = 0
    labtech_training: int = 0
    refresher_training: int = 0

    unscripted_events: int = 0
    scripted_events: int = 0


class EmployeeBonusRequest(BaseModel):
    name: str
    employee_id: str
    department: str

    lobbies: List[LobbyLog] = Field(default_factory=list)

    activities: ActivityCounts = Field(
        default_factory=ActivityCounts
    )


class BonusCalculationRequest(BaseModel):
    employees: List[EmployeeBonusRequest]


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():
    return {
        "message": "EMS Bonus Calculator API is running.",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    return {
        "status": "online"
    }


# ============================================================
# LOGIN
# ============================================================

@app.post("/auth/login")
def login(data: LoginRequest):

    username = data.username.strip().lower()

    user = USERS.get(username)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    if not hmac.compare_digest(
        data.password,
        user["password"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    token = create_token(username)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": username,
            "name": user["name"],
            "role": user["role"],
        },
    }


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/auth/me")
def current_user(user=Depends(get_current_user)):

    username = user["username"]

    account = USERS.get(username)

    if not account:
        raise HTTPException(
            status_code=401,
            detail="User not found.",
        )

    return {
        "username": username,
        "name": account["name"],
        "role": account["role"],
    }


# ============================================================
# BONUS RATE INFORMATION
# ============================================================

@app.get("/bonus-rates")
def get_bonus_rates(
    user=Depends(get_current_user),
):
    return {
        "rates": BONUS_RATES
    }


# ============================================================
# TIME CALCULATION
# ============================================================

def calculate_completed_hours(
    on_duty: str,
    off_duty: str,
) -> int:
    """
    Calculates completed hours only.

    Example:

    18:24 -> 19:04
    = 40 minutes
    = 0 paid hours

    18:24 -> 20:24
    = 2 hours
    = 2 paid hours
    """

    try:
        start = datetime.strptime(
            on_duty.strip(),
            "%H:%M"
        )

        end = datetime.strptime(
            off_duty.strip(),
            "%H:%M"
        )

        # Handles overnight shifts.
        if end < start:
            end += timedelta(days=1)

        difference = end - start

        total_seconds = int(
            difference.total_seconds()
        )

        completed_hours = total_seconds // 3600

        return completed_hours

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid time format: "
                f"{on_duty} - {off_duty}. "
                f"Use HH:MM format."
            ),
        )


# ============================================================
# LOBBY RATE
# ============================================================

def get_lobby_rate(
    lobby: str,
    department: str,
) -> int:

    lobby_key = lobby.lower().strip()
    department_key = department.lower().strip()

    # --------------------------------------------------------
    # HIGH COMMAND
    # --------------------------------------------------------

    if department_key in [
        "high command",
        "highcommand",
        "hc",
    ]:
        return BONUS_RATES["high_command_hour"]


    # --------------------------------------------------------
    # MEDICAL DEPARTMENT
    # --------------------------------------------------------

    if department_key in [
        "medical",
        "medical department",
        "ems",
    ]:

        rates = {
            "ph1": BONUS_RATES["day_ph1"],
            "ph2": BONUS_RATES["day_ph2"],

            "day ph1": BONUS_RATES["day_ph1"],
            "day ph2": BONUS_RATES["day_ph2"],

            "late ph1": BONUS_RATES["late_ph1"],
            "late ph2": BONUS_RATES["late_ph2"],

            "night ph1": BONUS_RATES["night_ph1"],
            "night ph2": BONUS_RATES["night_ph2"],

            "day on calls": BONUS_RATES["day_on_calls"],
            "late on calls": BONUS_RATES["late_on_calls"],
            "night on calls": BONUS_RATES["night_on_calls"],

            "standby": BONUS_RATES["standby"],
        }

        return rates.get(
            lobby_key,
            BONUS_RATES["high_command_hour"],
        )


    # --------------------------------------------------------
    # AMBULANCE
    # --------------------------------------------------------

    if department_key in [
        "ambulance",
        "ambulance department",
        "ambulance officer",
    ]:

        rates = {
            "day": BONUS_RATES["ambulance_day"],
            "day ambulance": BONUS_RATES["ambulance_day"],

            "late": BONUS_RATES["ambulance_late"],
            "late ambulance": BONUS_RATES["ambulance_late"],

            "night": BONUS_RATES["ambulance_night"],
            "night ambulance": BONUS_RATES["ambulance_night"],

            "standby": BONUS_RATES["standby"],
        }

        return rates.get(
            lobby_key,
            BONUS_RATES["ambulance_day"],
        )


    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    return BONUS_RATES["high_command_hour"]


# ============================================================
# LOBBY CALCULATION
# ============================================================

def calculate_lobbies(
    lobbies: List[LobbyLog],
    department: str,
):

    calculated_lobbies = []

    total_bonus = 0

    for lobby in lobbies:

        hours = calculate_completed_hours(
            lobby.on_duty,
            lobby.off_duty,
        )

        rate = get_lobby_rate(
            lobby.lobby,
            department,
        )

        bonus = hours * rate

        total_bonus += bonus

        calculated_lobbies.append({
            "lobby": lobby.lobby,
            "on_duty": lobby.on_duty,
            "off_duty": lobby.off_duty,
            "date": lobby.date,
            "completed_hours": hours,
            "rate_per_hour": rate,
            "bonus": bonus,
        })

    return calculated_lobbies, total_bonus


# ============================================================
# ACTIVITY CALCULATION
# ============================================================

def calculate_activities(
    activities: ActivityCounts,
):

    items = []

    total = 0


    # --------------------------------------------------------
    # CAPTCHA
    # --------------------------------------------------------

    if activities.captcha > 0:

        amount = (
            activities.captcha
            * BONUS_RATES["captcha"]
        )

        items.append({
            "type": "Captcha",
            "count": activities.captcha,
            "rate": BONUS_RATES["captcha"],
            "amount": amount,
        })

        total += amount


    # --------------------------------------------------------
    # DELIVERY
    # --------------------------------------------------------

    if activities.deliveries > 0:

        # $5,000 bonus
        delivery_bonus = (
            activities.deliveries
            * BONUS_RATES["delivery_bonus"]
        )

        # $5,000 per delivery
        delivery_paycheck = (
            activities.deliveries
            * BONUS_RATES["delivery_paycheck"]
        )

        amount = (
            delivery_bonus
            + delivery_paycheck
        )

        items.append({
            "type": "Delivery",
            "count": activities.deliveries,
            "rate": (
                BONUS_RATES["delivery_bonus"]
                + BONUS_RATES["delivery_paycheck"]
            ),
            "amount": amount,
        })

        total += amount


    # --------------------------------------------------------
    # FTO
    # --------------------------------------------------------

    training_items = [
        (
            "Day 1 Training",
            activities.day_1_training,
            BONUS_RATES["day_1_training"],
        ),
        (
            "Day 2 Training",
            activities.day_2_training,
            BONUS_RATES["day_2_training"],
        ),
        (
            "Labtech Training",
            activities.labtech_training,
            BONUS_RATES["labtech_training"],
        ),
        (
            "Refresher Training",
            activities.refresher_training,
            BONUS_RATES["refresher_training"],
        ),
    ]

    for name, count, rate in training_items:

        if count > 0:

            amount = count * rate

            items.append({
                "type": name,
                "count": count,
                "rate": rate,
                "amount": amount,
            })

            total += amount


    # --------------------------------------------------------
    # RESCUE OFFICER
    # --------------------------------------------------------

    event_items = [
        (
            "Unscripted Event",
            activities.unscripted_events,
            BONUS_RATES["unscripted_event"],
        ),
        (
            "Scripted Event",
            activities.scripted_events,
            BONUS_RATES["scripted_event"],
        ),
    ]

    for name, count, rate in event_items:

        if count > 0:

            amount = count * rate

            items.append({
                "type": name,
                "count": count,
                "rate": rate,
                "amount": amount,
            })

            total += amount


    return items, total


# ============================================================
# CALCULATE ONE EMPLOYEE
# ============================================================

def calculate_employee(
    employee: EmployeeBonusRequest,
):

    lobby_items, lobby_total = calculate_lobbies(
        employee.lobbies,
        employee.department,
    )

    activity_items, activity_total = calculate_activities(
        employee.activities,
    )

    total = lobby_total + activity_total

    return {
        "name": employee.name,
        "employee_id": employee.employee_id,
        "department": employee.department,

        "lobbies": lobby_items,
        "activities": activity_items,

        "lobby_total": lobby_total,
        "activity_total": activity_total,

        "total": total,
    }


# ============================================================
# CALCULATE ALL BONUSES
# ============================================================

@app.post("/calculate")
def calculate_bonus(
    data: BonusCalculationRequest,
    user=Depends(get_current_user),
):

    employees = []

    department_totals: Dict[str, int] = {}

    grand_total = 0

    for employee in data.employees:

        result = calculate_employee(employee)

        employees.append(result)

        department = employee.department

        if department not in department_totals:
            department_totals[department] = 0

        department_totals[department] += result["total"]

        grand_total += result["total"]


    return {
        "employees": employees,
        "department_totals": department_totals,
        "grand_total": grand_total,
    }


# ============================================================
# MONEY FORMAT
# ============================================================

def money(amount: int) -> str:
    return f"${amount:,.0f}"


# ============================================================
# DISCORD REPORT GENERATOR
# ============================================================

def generate_employee_line(
    employee: Dict[str, Any]
) -> str:

    parts = []


    # --------------------------------------------------------
    # LOBBIES
    # --------------------------------------------------------

    for lobby in employee["lobbies"]:

        hours = lobby["completed_hours"]

        if hours <= 0:
            continue

        lobby_name = lobby["lobby"]

        amount = lobby["bonus"]

        parts.append(
            f"{hours}Hr {lobby_name} = {money(amount)}"
        )


    # --------------------------------------------------------
    # ACTIVITIES
    # --------------------------------------------------------

    for activity in employee["activities"]:

        count = activity["count"]

        amount = activity["amount"]

        activity_type = activity["type"]

        parts.append(
            f"{count}x {activity_type} = {money(amount)}"
        )


    if not parts:
        parts.append("No payable bonuses")


    details = " , ".join(parts)

    return (
        f"{employee['name']} | "
        f"{employee['employee_id']} "
        f"({details}) "
        f"Total = {money(employee['total'])}"
    )


# ============================================================
# REPORT
# ============================================================

@app.post("/calculate/report")
def calculate_report(
    data: BonusCalculationRequest,
    user=Depends(get_current_user),
):

    results = []

    department_groups: Dict[
        str,
        List[Dict[str, Any]]
    ] = {}

    department_totals: Dict[str, int] = {}


    # --------------------------------------------------------
    # CALCULATE
    # --------------------------------------------------------

    for employee in data.employees:

        result = calculate_employee(employee)

        results.append(result)

        department = employee.department

        if department not in department_groups:
            department_groups[department] = []

        department_groups[department].append(
            result
        )

        department_totals[department] = (
            department_totals.get(
                department,
                0
            )
            + result["total"]
        )


    # --------------------------------------------------------
    # BUILD REPORT
    # --------------------------------------------------------

    lines = []

    grand_total = sum(
        department_totals.values()
    )


    for department, employees in department_groups.items():

        lines.append(
            "==================="
        )

        lines.append(
            department
        )

        lines.append(
            "==================="
        )

        for employee in employees:

            lines.append(
                generate_employee_line(
                    employee
                )
            )

            lines.append("")


        lines.append(
            f"Department Total: "
            f"{money(department_totals[department])}"
        )

        lines.append(
            "==================="
        )


    lines.append(
        "===================================="
    )

    lines.append(
        f"All Total = {money(grand_total)}"
    )

    lines.append(
        "===================================="
    )

    lines.append(
        "Bonus missing? DM me with logs or bodycam proof."
    )

    lines.append(
        "Partial shifts are not paid; hourly bonuses require a completed hour."
    )

    report = "\n".join(lines)

    return {
        "report": report,
        "department_totals": department_totals,
        "grand_total": grand_total,
        "employees": results,
    }


# ============================================================
# EXAMPLE / TEST CALCULATION
# ============================================================

@app.get("/example")
def example(
    user=Depends(get_current_user),
):

    example_data = BonusCalculationRequest(
        employees=[
            EmployeeBonusRequest(
                name="Kevin Sims",
                employee_id="163100",
                department="Human Resources",
                activities=ActivityCounts(
                    day_1_training=1
                ),
            ),

            EmployeeBonusRequest(
                name="Luna Valente",
                employee_id="463928",
                department="Human Resources",
                activities=ActivityCounts(
                    day_1_training=1
                ),
            ),

            EmployeeBonusRequest(
                name="Kikita Sokolov",
                employee_id="558052",
                department="Rescue Officer",
                lobbies=[
                    LobbyLog(
                        lobby="Day PH2",
                        on_duty="10:00",
                        off_duty="11:00",
                    ),
                ],
                activities=ActivityCounts(
                    unscripted_events=1
                ),
            ),
        ]
    )

    return calculate_report(
        example_data,
        user,
    )


# ============================================================
# ERROR HANDLER
# ============================================================

@app.get("/bonus-rates/public")
def public_bonus_rates():
    """
    Public endpoint for displaying the current bonus structure
    before login if required by the frontend.
    """

    return {
        "rates": BONUS_RATES
    }


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )