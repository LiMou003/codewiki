import adalflow as adal

from api.config import configs, get_embedder_type


def get_embedder(is_local_ollama: bool = False, use_google_embedder: bool = False, embedder_type: str = None, dimension: int = None) -> adal.Embedder:
    embedder_config = configs["embedder_dashscope"]

    model_client_class = embedder_config["model_client"]
    if "initialize_kwargs" in embedder_config:
        model_client = model_client_class(**embedder_config["initialize_kwargs"])
    else:
        model_client = model_client_class()

    model_kwargs = dict(embedder_config.get("model_kwargs", {}))
    if dimension is not None:
        model_kwargs["dimension"] = dimension

    embedder_kwargs = {"model_client": model_client, "model_kwargs": model_kwargs}

    embedder = adal.Embedder(**embedder_kwargs)

    if "batch_size" in embedder_config:
        embedder.batch_size = embedder_config["batch_size"]
    return embedder
