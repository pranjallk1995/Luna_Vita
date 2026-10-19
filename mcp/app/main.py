"""Compose and run the Luna Vita MCP and HTTP server."""

from mcp.server.fastmcp import FastMCP

from .branding import ServerBranding
from .config import AppConfig
from .database import Database
from .http_routes import LunaVitaHTTPRoutes
from .mcp_tools import LunaVitaMCPTools
from .repositories import (
    AnalysisRangeRepository,
    DailyLogRepository,
    FoodRepository,
    MeasurementRepository,
    RecommendationRepository,
    VerdictRepository,
)
from .services import (
    AnalysisService,
    BodyCompositionService,
    DayContextService,
    FoodService,
    LunaVitaService,
    MeasurementService,
    ProfileService,
    ReportService,
)
from .visia import VisiaImageCatalog


class LunaVitaApplication:
    """Compose and own the concrete Luna Vita dependencies."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.database = Database(config.database_url)
        self.database.open()
        self.database.initialize_schema()
        self.service = self._build_service()
        self.branding = ServerBranding()
        self.mcp = FastMCP(
            "LunaVita",
            icons=self.branding.mcp_icons(),
            host=config.host,
            port=config.port,
            stateless_http=True,
            json_response=True,
        )
        LunaVitaMCPTools(self.mcp, self.service)
        LunaVitaHTTPRoutes(self.mcp, self.service, self.branding)

    def _build_service(self) -> LunaVitaService:
        food_entries = FoodRepository(self.database)
        food = FoodService(food_entries, VisiaImageCatalog(
            self.config.visia_api_url, self.config.placeholder_image_id
        ))
        measurement_entries = MeasurementRepository(self.database)
        recommendations = RecommendationRepository(self.database)
        measurements = MeasurementService(measurement_entries)
        days = DayContextService(DailyLogRepository(self.database))
        return LunaVitaService(
            food=food,
            measurements=measurements,
            body=BodyCompositionService(measurement_entries, recommendations),
            days=days,
            profile=ProfileService(recommendations),
            reports=ReportService(food, measurements, days),
            analysis=AnalysisService(
                food_entries,
                VerdictRepository(self.database),
                AnalysisRangeRepository(self.database),
            ),
        )

    def run(self) -> None:
        try:
            self.mcp.run(transport="streamable-http")
        finally:
            self.database.close()


application = LunaVitaApplication(AppConfig.from_env())
mcp = application.mcp
app = mcp.streamable_http_app()

if __name__ == "__main__":
    application.run()
