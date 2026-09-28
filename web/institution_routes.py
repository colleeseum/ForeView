"""Read-only institution capability discovery."""

from flask import Blueprint, jsonify

from institution_support import institution_registry

blueprint = Blueprint("institutions", __name__)


@blueprint.get("/api/institutions")
def institutions():
    providers = []
    for provider in institution_registry().providers:
        connection = provider.connection
        providers.append(
            {
                "key": provider.key,
                "display_name": provider.display_name,
                "aliases": list(provider.aliases),
                "importers": [
                    {
                        "name": importer.name,
                        "document_type": importer.document_type,
                        "help_text": importer.help_text,
                    }
                    for importer in provider.importers
                ],
                "connection": (
                    {
                        "operations": sorted(
                            operation.value for operation in connection.operations
                        ),
                        "status_path": connection.status_path,
                        "connect_path": connection.connect_path,
                        "sync_path": connection.sync_path,
                        "callback_path": connection.callback_path,
                    }
                    if connection
                    else None
                ),
                "help_topics": [
                    {"key": topic.key, "title": topic.title, "body": topic.body}
                    for topic in provider.help_topics
                ],
            }
        )
    return jsonify({"institutions": providers})
