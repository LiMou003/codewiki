import adalflow as adal

from api.config import configs


def get_embedder(is_local_ollama: bool = False, use_google_embedder: bool = False, embedder_type: str = None) -> adal.Embedder:
    """Get dashscope embedder.
    
    Args:
        is_local_ollama: Unused, kept for backward compatibility
        use_google_embedder: Unused, kept for backward compatibility
        embedder_type: Unused, kept for backward compatibility
    
    Returns:
        adal.Embedder: Configured Dashscope embedder instance
    """
    embedder_config = configs.get("embedder_dashscope") or configs.get("embedder")

    # --- Initialize Embedder ---
    model_client_class = embedder_config["model_client"]
    if "initialize_kwargs" in embedder_config:
        model_client = model_client_class(**embedder_config["initialize_kwargs"])
    else:
        model_client = model_client_class()
    
    # Create embedder with basic parameters
    embedder_kwargs = {"model_client": model_client, "model_kwargs": embedder_config["model_kwargs"]}
    
    embedder = adal.Embedder(**embedder_kwargs)
    
    # Set batch_size as an attribute if available (not a constructor parameter)
    if "batch_size" in embedder_config:
        embedder.batch_size = embedder_config["batch_size"]
    return embedder
