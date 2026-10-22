from dmr.routing import Router, path

from tickfeeddmr.ai.api.controllers.chat import AiChatController
from tickfeeddmr.ai.api.controllers.status import AiStatusController

router = Router(
    "ai/",
    [
        path("status", AiStatusController.as_view(), name="ai-status"),
        path("chat", AiChatController.as_view(), name="ai-chat"),
    ],
)
