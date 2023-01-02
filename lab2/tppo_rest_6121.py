import os
import threading

from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse

from lab1.tppo_server_6121 import BedReanimation

app = FastAPI(
    title="Bed Reanimation API",
    description="API for Bed Reanimation",
    version="1.0.0",
    contact={
        "name": "Якимов Я.Д",
        "email": "yaroslav@itmo.ru",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "angles",
            "description": "Operations with angles",
        },
        {
            "name": "height",
            "description": "Operations with height",
        },
        {
            "name": "weight",
            "description": "Operations with weight",
        },
    ],
)
dir_path = os.path.dirname(os.path.realpath(__file__))

# Rest API for the TPPO lab. Use class from lab1/tppo_server_6121.py as a template for this lab.
bed = BedReanimation(f'{dir_path}/../lab1/device.csv')
t1 = threading.Thread(target=bed.listen_file)
t1.daemon = True
t1.start()


class Angles(BaseModel):
    back: int = Field(ge=0, le=50, description="Back angle of the bed. Must be in range [0, 50]", example=30)
    hip: int = Field(ge=-15, le=15, description="Hip angle of the bed. Must be in range [-15, 15]", example=10)
    ankle: int = Field(ge=0, le=30, description="Ankle angle of the bed. Must be in range [0, 30]", example=20)


class Height(BaseModel):
    height: int = Field(ge=0, le=100, description="Height of the bed. Must be in range [0, 100]", example=100)


class Weight(BaseModel):
    weight: int = Field(ge=0, le=300, description="Weight of the patient. Must be in range [0, 300]", example=80)


class ReanimationBed(BaseModel):
    angles: Angles
    height: int = Field(ge=0, le=100, description="Height of the bed. Must be in range [0, 100]", example=100)
    weight: int = Field(ge=0, le=300, description="Weight of the patient. Must be in range [0, 300]", example=80)


class Response(BaseModel):
    status: str = Field(description="Status of the request", example="success/error")
    message: str = Field(description="Message of the request", example="Bed angles changed")


@app.get("/api/v1/reanimation-bed",
         response_model=ReanimationBed,
         summary="All parameters of the bed",
         description="Get all parameters of the bed")
async def get_all():
    angles_data = bed.get_angles().decode().split(',')
    return {
        "angles": {
            "back": angles_data[0],
            "hip": angles_data[1],
            "ankle": angles_data[2],
        },
        "height": bed.get_height(),
        "weight": bed.get_weight(),
    }


@app.get("/api/v1/reanimation-bed/angles",
         response_model=Angles,
         tags=["angles"],
         summary="Angles of the bed",
         description="Get angles of the bed")
async def get_angles():
    data = bed.get_angles().decode().split(',')
    return {
        "back": data[0],
        "hip": data[1],
        "ankle": data[2]
    }


@app.get("/api/v1/reanimation-bed/height",
         response_model=Height,
         tags=["height"],
         summary="Height of the bed",
         description="Get height of the bed in cm")
async def get_height():
    return {"height": bed.get_height().decode()}


@app.get("/api/v1/reanimation-bed/weight",
         response_model=Weight,
         tags=["weight"],
         summary="Weight of the patient",
         description="Get weight of the patient in kg")
async def get_weight():
    return {"weight": bed.get_weight().decode()}


@app.put("/api/v1/reanimation-bed/angles",
         response_model=Response,
         tags=["angles"],
         summary="Angles of the bed",
         description="Set angles of the bed")
async def set_angles(angles: Angles):
    result = bed.set_angles_to_device(angles.back, angles.hip, angles.ankle).decode()
    if '!Success' in result:
        return {"status": "success", "message": "Bed angles changed"}
    else:
        return {"status": "error", "message": "Bed angles not changed"}


@app.put("/api/v1/reanimation-bed/height",
         response_model=Response,
         tags=["height"],
         summary="Height of the bed",
         description="Set height of the bed in cm")
async def set_height(height: Height = Body()):
    result = bed.set_height_to_device(height.height).decode()
    if '!Success' in result:
        return {"status": "success", "message": "Bed height changed"}
    else:
        return {"status": "error", "message": "Bed height not changed"}


@app.put("/api/v1/reanimation-bed/weight",
         response_model=Response,
         tags=["weight"],
         summary="Weight of the patient",
         description="Set weight of the patient in kg")
async def set_weight(weight: Weight = Body()):
    result = bed.set_weight_to_device(weight.weight).decode()
    if '!Success' in result:
        return {"status": "success", "message": "Patient weight changed"}
    else:
        return {"status": "error", "message": "Patient weight not changed"}


@app.api_route("/{path_name:path}", methods=["GET"], response_class=RedirectResponse)
async def read_root():
    return RedirectResponse(url="/docs")
