from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import os
import base64
import hashlib
import hmac
import json


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

        # Add your Vercel frontend URL here after deployment.
        # Example:
        # "https://ems-bonus-calculator.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# BASIC CONFIGURATION
# ============================================================

TOKEN_SECRET = os.getenv(
    "TOKEN_SECRET",
    "ems-bonus-calculator-change-this-secret"
)


# ============================================================
# USERS
# ============================================================
# Temporary login system.
# These can later be moved to a database.

USERS = {
    "admin": {
        "password": "admin123",
        "name": "EMS Admin",
        "role": "Admin",
    },
    "hr": {
        "password": "hr123",
        "name": "Human Resources",
        "role": "HR",
    },
    "manager": {
        "password": "manager123",
        "name": "EMS Manager",
        "role": "Manager",
    },
}


# ============================================================
# BONUS RATES
# ============================================================

BONUS_RATES = {

    # --------------------------------------------------------
    # LABTECH
    # --------------------------------------------------------

    "labtech": {
        "captcha": 10000,

        # $5,000 bonus + $5,000 normal delivery payment
        "delivery_bonus": 5000,
        "delivery_payment": 5000,

        "day_1_training": 55000,
        "day_2_training": 50000,
        "labtech_training": 30000,
        "refresher_training": 30000,
    },

    # --------------------------------------------------------
    # FTO
    # --------------------------------------------------------

    "fto": {
        "day_1_training": 55000,
        "day_2_training": 50000,
        "labtech_training": 30000,
        "refresher_training": 30000,
    },

    # --------------------------------------------------------
    # RESCUE OFFICER
    # --------------------------------------------------------

    "rescue": {
        "unscripted_event": 15000,
        "scripted_event": 25000,
    },

    # --------------------------------------------------------
    # HIGH COMMAND
    # --------------------------------------------------------

    "high_command": {
        "lobby_hour": 10000,
    },

    # --------------------------------------------------------
    # MEDICAL DEPARTMENT
    # --------------------------------------------------------

    "medical": {
        "day_ph1": 10000,
        "day_ph2": 10000,

        "night_ph1": 20000,
        "night_ph2": 20000,

        "late_ph1": 20000,
        "late_ph2": 20000,

        "day_on_call": 10000,
        "night_on_call": 20000,
        "late_on_call": 20000,

        "standby": 10000,
    },

    # --------------------------------------------------------
    # AMBULANCE
    # --------------------------------------------------------

    "ambulance": {
        "day_lobby": 10000,
        "night_lobby": 20000,
        "late_lobby": 20000,

        "day_on_call": 10000,
        "night_on_call": 20000,
        "late_on_call": 20000,

        "standby": 10000,
    },
}


# ============================================================
# DEPARTMENTS
# ============================================================

DEPARTMENTS = [
    "Human Resources",
    "Medical Department",
    "Ambulance",
    "Labtech",
    "Rescue Officer",
    "High Command",
]


# ============================================================
# MODELS
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class LobbyLog(BaseModel):
    lobby: str
    start_time: str
    end_time: str
    date: Optional[str] = None


class ActivityCounts(BaseModel):
    captcha: int = Field(default=0, ge=0)
    deliveries: int = Field(default=0, ge=0)

    day_1_training: int = Field(default=0, ge=0)
    day_2_training: int = Field(default=0, ge=0)
    labtech_training: int = Field(default=0, ge=0)
    refresher_training: int = Field(default=0, ge=0)

    unscripted_events: int = Field(default=0, ge=0)
    scripted_events: int = Field(default=0, ge=0)

    day_ph1_hours: int = Field(default=0, ge=0)
    day_ph2_hours: int = Field(default=0, ge=0)

    night_ph1_hours: int = Field(default=0, ge=0)
    night_ph2_hours: int = Field(default=0, ge=0)

    late_ph1_hours: int = Field(default=0, ge=0)
    late_ph2_hours: int = Field(default=0, ge=0)

    day_on_call_hours: int = Field(default=0, ge=0)
    night_on_call_hours: int = Field(default=0, ge=0)
    late_on_call_hours: int = Field(default=0, ge=0)

    day_lobby_hours: int = Field(default=0, ge=0)
    night_lobby_hours: int = Field(default=0, ge=0)
    late_lobby_hours: int = Field(default=0, ge=0)

    standby_hours: int = Field(default=0, ge=0)


class EmployeeBonusRequest(BaseModel):
    name: str
    employee_id: str
    department: str
    activities: ActivityCounts = ActivityCounts()
    lobby_logs: List[LobbyLog] = []


class BonusCalculationRequest(BaseModel):
    employees: List[EmployeeBonusRequest]


# ============================================================
# TOKEN FUNCTIONS
# ============================================================

def create_token(username: str) -> str:
    """
    Creates a simple signed token using HMAC.
    This is suitable for this calculator's current login system.
    """

    payload = {
        "username": username,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    payload_json = json.dumps(
        payload,
        separators=(",", ":")
    ).encode()

    encoded_payload = base64.urlsafe_b64encode(
        payload_json
    ).decode()

    signature = hmac.new(
        TOKEN_SECRET.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return f"{encoded_payload}.{signature}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        if not token or "." not in token:
            return None

        encoded_payload, signature = token.split(".", 1)

        expected_signature = hmac.new(
            TOKEN_SECRET.encode(),
            encoded_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected_signature
        ):
            return None

        payload_json = base64.urlsafe_b64decode(
            encoded_payload.encode()
        )

        return json.loads(payload_json)

    except Exception:
        return None


def get_current_user(
    authorization: Optional[str]
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required."
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format."
        )

    token = authorization.replace(
        "Bearer ",
        "",
        1
    ).strip()

    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token."
        )

    username = payload.get("username")

    if username not in USERS:
        raise HTTPException(
            status_code=401,
            detail="User not found."
        )

    return {
        "username": username,
        **USERS[username],
    }


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def money(amount: int) -> str:
    return f"${amount:,.0f}"


def completed_hours_from_minutes(minutes: int) -> int:
    """
    Only completed hours are paid.
    Example:
    59 minutes = 0 hours
    60 minutes = 1 hour
    119 minutes = 1 hour
    120 minutes = 2 hours
    """

    if minutes <= 0:
        return 0

    return minutes // 60


def parse_time_to_minutes(value: str) -> int:
    """
    Converts HH:MM into minutes from midnight.
    """

    value = value.strip()

    dt = datetime.strptime(
        value,
        "%H:%M"
    )

    return dt.hour * 60 + dt.minute


def calculate_lobby_hours(
    start_time: str,
    end_time: str
) -> int:

    try:
        start = parse_time_to_minutes(start_time)
        end = parse_time_to_minutes(end_time)

        # Overnight shift
        if end < start:
            end += 24 * 60

        duration = end - start

        return completed_hours_from_minutes(
            duration
        )

    except Exception:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid time format: "
                f"{start_time} - {end_time}. "
                f"Use HH:MM."
            )
        )


def calculate_lobby_log_bonus(
    lobby: LobbyLog
) -> Dict[str, Any]:

    hours = calculate_lobby_hours(
        lobby.start_time,
        lobby.end_time
    )

    lobby_name = lobby.lobby.lower().strip()

    rate = 0

    if "day ph1" in lobby_name:
        rate = BONUS_RATES["medical"]["day_ph1"]

    elif "day ph2" in lobby_name:
        rate = BONUS_RATES["medical"]["day_ph2"]

    elif "night ph1" in lobby_name:
        rate = BONUS_RATES["medical"]["night_ph1"]

    elif "night ph2" in lobby_name:
        rate = BONUS_RATES["medical"]["night_ph2"]

    elif "late ph1" in lobby_name:
        rate = BONUS_RATES["medical"]["late_ph1"]

    elif "late ph2" in lobby_name:
        rate = BONUS_RATES["medical"]["late_ph2"]

    elif "day on call" in lobby_name:
        rate = BONUS_RATES["medical"]["day_on_call"]

    elif "night on call" in lobby_name:
        rate = BONUS_RATES["medical"]["night_on_call"]

    elif "late on call" in lobby_name:
        rate = BONUS_RATES["medical"]["late_on_call"]

    elif "day lobby" in lobby_name:
        rate = BONUS_RATES["ambulance"]["day_lobby"]

    elif "night lobby" in lobby_name:
        rate = BONUS_RATES["ambulance"]["night_lobby"]

    elif "late lobby" in lobby_name:
        rate = BONUS_RATES["ambulance"]["late_lobby"]

    elif "standby" in lobby_name:
        rate = BONUS_RATES["high_command"]["lobby_hour"]

    else:
        rate = BONUS_RATES["medical"]["day_ph1"]

    bonus = hours * rate

    return {
        "lobby": lobby.lobby,
        "start_time": lobby.start_time,
        "end_time": lobby.end_time,
        "date": lobby.date,
        "completed_hours": hours,
        "rate_per_hour": rate,
        "bonus": bonus,
    }


# ============================================================
# CALCULATE EMPLOYEE BONUS
# ============================================================

def calculate_employee(
    employee: EmployeeBonusRequest
) -> Dict[str, Any]:

    activities = employee.activities

    department = employee.department.lower().strip()

    breakdown = []
    total = 0

    # --------------------------------------------------------
    # LABTECH
    # --------------------------------------------------------

    if department == "labtech":

        if activities.captcha:
            amount = (
                activities.captcha
                * BONUS_RATES["labtech"]["captcha"]
            )

            breakdown.append({
                "activity": "Captcha",
                "count": activities.captcha,
                "rate": BONUS_RATES["labtech"]["captcha"],
                "amount": amount,
            })

            total += amount

        if activities.deliveries:
            bonus_amount = (
                activities.deliveries
                * BONUS_RATES["labtech"]["delivery_bonus"]
            )

            breakdown.append({
                "activity": "Delivery Bonus",
                "count": activities.deliveries,
                "rate": BONUS_RATES["labtech"]["delivery_bonus"],
                "amount": bonus_amount,
            })

            total += bonus_amount

        if activities.day_1_training:
            amount = (
                activities.day_1_training
                * BONUS_RATES["labtech"]["day_1_training"]
            )

            breakdown.append({
                "activity": "Day 1 Training",
                "count": activities.day_1_training,
                "rate": BONUS_RATES["labtech"]["day_1_training"],
                "amount": amount,
            })

            total += amount

        if activities.day_2_training:
            amount = (
                activities.day_2_training
                * BONUS_RATES["labtech"]["day_2_training"]
            )

            breakdown.append({
                "activity": "Day 2 Training",
                "count": activities.day_2_training,
                "rate": BONUS_RATES["labtech"]["day_2_training"],
                "amount": amount,
            })

            total += amount

        if activities.labtech_training:
            amount = (
                activities.labtech_training
                * BONUS_RATES["labtech"]["labtech_training"]
            )

            breakdown.append({
                "activity": "Labtech Training",
                "count": activities.labtech_training,
                "rate": BONUS_RATES["labtech"]["labtech_training"],
                "amount": amount,
            })

            total += amount

        if activities.refresher_training:
            amount = (
                activities.refresher_training
                * BONUS_RATES["labtech"]["refresher_training"]
            )

            breakdown.append({
                "activity": "Refresher Training",
                "count": activities.refresher_training,
                "rate": BONUS_RATES["labtech"]["refresher_training"],
                "amount": amount,
            })

            total += amount

    # --------------------------------------------------------
    # FTO
    # --------------------------------------------------------

    elif department in ["fto", "human resources", "hr"]:

        if activities.day_1_training:
            amount = (
                activities.day_1_training
                * BONUS_RATES["fto"]["day_1_training"]
            )

            breakdown.append({
                "activity": "Day 1 Training",
                "count": activities.day_1_training,
                "rate": BONUS_RATES["fto"]["day_1_training"],
                "amount": amount,
            })

            total += amount

        if activities.day_2_training:
            amount = (
                activities.day_2_training
                * BONUS_RATES["fto"]["day_2_training"]
            )

            breakdown.append({
                "activity": "Day 2 Training",
                "count": activities.day_2_training,
                "rate": BONUS_RATES["fto"]["day_2_training"],
                "amount": amount,
            })

            total += amount

        if activities.labtech_training:
            amount = (
                activities.labtech_training
                * BONUS_RATES["fto"]["labtech_training"]
            )

            breakdown.append({
                "activity": "Labtech Training",
                "count": activities.labtech_training,
                "rate": BONUS_RATES["fto"]["labtech_training"],
                "amount": amount,
            })

            total += amount

        if activities.refresher_training:
            amount = (
                activities.refresher_training
                * BONUS_RATES["fto"]["refresher_training"]
            )

            breakdown.append({
                "activity": "Refresher Training",
                "count": activities.refresher_training,
                "rate": BONUS_RATES["fto"]["refresher_training"],
                "amount": amount,
            })

            total += amount

    # --------------------------------------------------------
    # RESCUE OFFICER
    # --------------------------------------------------------

    elif department in [
        "rescue",
        "rescue officer",
    ]:

        if activities.unscripted_events:
            amount = (
                activities.unscripted_events
                * BONUS_RATES["rescue"]["unscripted_event"]
            )

            breakdown.append({
                "activity": "Unscripted Event",
                "count": activities.unscripted_events,
                "rate": BONUS_RATES["rescue"]["unscripted_event"],
                "amount": amount,
            })

            total += amount

        if activities.scripted_events:
            amount = (
                activities.scripted_events
                * BONUS_RATES["rescue"]["scripted_event"]
            )

            breakdown.append({
                "activity": "Scripted Event",
                "count": activities.scripted_events,
                "rate": BONUS_RATES["rescue"]["scripted_event"],
                "amount": amount,
            })

            total += amount

    # --------------------------------------------------------
    # MEDICAL DEPARTMENT
    # --------------------------------------------------------

    elif department in [
        "medical",
        "medical department",
    ]:

        hourly_items = [
            (
                "Day PH1",
                activities.day_ph1_hours,
                BONUS_RATES["medical"]["day_ph1"],
            ),
            (
                "Day PH2",
                activities.day_ph2_hours,
                BONUS_RATES["medical"]["day_ph2"],
            ),
            (
                "Night PH1",
                activities.night_ph1_hours,
                BONUS_RATES["medical"]["night_ph1"],
            ),
            (
                "Night PH2",
                activities.night_ph2_hours,
                BONUS_RATES["medical"]["night_ph2"],
            ),
            (
                "Late PH1",
                activities.late_ph1_hours,
                BONUS_RATES["medical"]["late_ph1"],
            ),
            (
                "Late PH2",
                activities.late_ph2_hours,
                BONUS_RATES["medical"]["late_ph2"],
            ),
            (
                "Day On Calls",
                activities.day_on_call_hours,
                BONUS_RATES["medical"]["day_on_call"],
            ),
            (
                "Night On Calls",
                activities.night_on_call_hours,
                BONUS_RATES["medical"]["night_on_call"],
            ),
            (
                "Late On Calls",
                activities.late_on_call_hours,
                BONUS_RATES["medical"]["late_on_call"],
            ),
            (
                "Standby",
                activities.standby_hours,
                BONUS_RATES["medical"]["standby"],
            ),
        ]

        for name, hours, rate in hourly_items:

            if hours > 0:

                amount = hours * rate

                breakdown.append({
                    "activity": name,
                    "hours": hours,
                    "rate": rate,
                    "amount": amount,
                })

                total += amount

    # --------------------------------------------------------
    # AMBULANCE
    # --------------------------------------------------------

    elif department == "ambulance":

        hourly_items = [
            (
                "Day Lobby",
                activities.day_lobby_hours,
                BONUS_RATES["ambulance"]["day_lobby"],
            ),
            (
                "Night Lobby",
                activities.night_lobby_hours,
                BONUS_RATES["ambulance"]["night_lobby"],
            ),
            (
                "Late Lobby",
                activities.late_lobby_hours,
                BONUS_RATES["ambulance"]["late_lobby"],
            ),
            (
                "Day On Calls",
                activities.day_on_call_hours,
                BONUS_RATES["ambulance"]["day_on_call"],
            ),
            (
                "Night On Calls",
                activities.night_on_call_hours,
                BONUS_RATES["ambulance"]["night_on_call"],
            ),
            (
                "Late On Calls",
                activities.late_on_call_hours,
                BONUS_RATES["ambulance"]["late_on_call"],
            ),
            (
                "Standby",
                activities.standby_hours,
                BONUS_RATES["ambulance"]["standby"],
            ),
        ]

        for name, hours, rate in hourly_items:

            if hours > 0:

                amount = hours * rate

                breakdown.append({
                    "activity": name,
                    "hours": hours,
                    "rate": rate,
                    "amount": amount,
                })

                total += amount

    # --------------------------------------------------------
    # HIGH COMMAND
    # --------------------------------------------------------

    elif department in [
        "high command",
        "high_command",
    ]:

        hours = activities.standby_hours

        if hours > 0:

            amount = (
                hours
                * BONUS_RATES["high_command"]["lobby_hour"]
            )

            breakdown.append({
                "activity": "Lobby / Standby",
                "hours": hours,
                "rate": BONUS_RATES["high_command"]["lobby_hour"],
                "amount": amount,
            })

            total += amount

        if activities.unscripted_events:
            amount = (
                activities.unscripted_events
                * BONUS_RATES["rescue"]["unscripted_event"]
            )

            breakdown.append({
                "activity": "Unscripted Event",
                "count": activities.unscripted_events,
                "rate": BONUS_RATES["rescue"]["unscripted_event"],
                "amount": amount,
            })

            total += amount

        if activities.scripted_events:
            amount = (
                activities.scripted_events
                * BONUS_RATES["rescue"]["scripted_event"]
            )

            breakdown.append({
                "activity": "Scripted Event",
                "count": activities.scripted_events,
                "rate": BONUS_RATES["rescue"]["scripted_event"],
                "amount": amount,
            })

            total += amount

    # --------------------------------------------------------
    # LOBBY LOGS
    # --------------------------------------------------------

    lobby_results = []

    for lobby in employee.lobby_logs:

        result = calculate_lobby_log_bonus(
            lobby
        )

        lobby_results.append(result)

        total += result["bonus"]

    return {
        "name": employee.name,
        "employee_id": employee.employee_id,
        "department": employee.department,
        "breakdown": breakdown,
        "lobby_logs": lobby_results,
        "total": total,
        "formatted_total": money(total),
    }


# ============================================================
# ROOT / HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "message": "EMS Bonus Calculator API is running.",
        "version": "1.0.0",
        "status": "online",
    }


@app.get("/healthz")
def health_check():
    return {
        "status": "healthy"
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
            detail="Invalid username or password."
        )

    if data.password != user["password"]:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
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
def auth_me(
    authorization: Optional[str] = Header(default=None)
):

    user = get_current_user(
        authorization
    )

    return {
        "user": user
    }


# ============================================================
# DEPARTMENTS
# ============================================================

@app.get("/departments")
def get_departments(
    authorization: Optional[str] = Header(default=None)
):

    get_current_user(
        authorization
    )

    return {
        "departments": DEPARTMENTS
    }


# ============================================================
# BONUS RATES
# ============================================================

@app.get("/bonus-rates")
def get_bonus_rates(
    authorization: Optional[str] = Header(default=None)
):

    get_current_user(
        authorization
    )

    return {
        "rates": BONUS_RATES
    }


# ============================================================
# CALCULATE SINGLE EMPLOYEE
# ============================================================

@app.post("/calculate")
def calculate_bonus(
    request: EmployeeBonusRequest,
    authorization: Optional[str] = Header(default=None)
):

    get_current_user(
        authorization
    )

    return calculate_employee(
        request
    )


# ============================================================
# CALCULATE MULTIPLE EMPLOYEES
# ============================================================

@app.post("/calculate/report")
def calculate_report(
    request: BonusCalculationRequest,
    authorization: Optional[str] = Header(default=None)
):

    get_current_user(
        authorization
    )

    results = []

    department_totals = {}

    grand_total = 0

    for employee in request.employees:

        result = calculate_employee(
            employee
        )

        results.append(result)

        department = employee.department

        department_totals.setdefault(
            department,
            0
        )

        department_totals[department] += (
            result["total"]
        )

        grand_total += result["total"]

    return {
        "employees": results,
        "department_totals": department_totals,
        "grand_total": grand_total,
        "formatted_grand_total": money(
            grand_total
        ),
    }


# ============================================================
# EXAMPLE
# ============================================================

@app.get("/example")
def example():

    example_employee = EmployeeBonusRequest(
        name="Kevin Sims",
        employee_id="163100",
        department="Human Resources",
        activities=ActivityCounts(
            day_1_training=1
        ),
    )

    return calculate_employee(
        example_employee
    )


# ============================================================
# RUN LOCALLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )