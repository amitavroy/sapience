# Import every model module here so Alembic autogenerate sees it.
from app.models.chunk import Chunk  # noqa: F401
from app.models.collection import Collection, CollectionMember, CollectionRole  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.document import Document, DocumentStatus  # noqa: F401
from app.models.user import User  # noqa: F401
