from flask import Blueprint, jsonify

from services.dashboard_query import DashboardQuery
from web.dependencies import dependency

blueprint = Blueprint("dashboard", __name__)


@blueprint.get("/api/dashboard")
def dashboard_data():
    with dependency("connect")() as connection:
        return jsonify(DashboardQuery(connection).execute())
