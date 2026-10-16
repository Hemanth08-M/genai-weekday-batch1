import platform
print(f"Hello from inside a container! Python {platform.python_version()}")



"""
1. CLI(client) reads Dockerfile + .dockerignore, sends them to the daemon -> builder
2. Builder resolves FROM: auth, metadata, pull base image layers
3. Context: send your folder's files (minus ignored ones) to the builder
4. Run instructions in order, each making a layer:
     WORKDIR /app   -> layer
     COPY app.py .  -> layer (file taken from the context)
     CMD            -> no layer, just metadata
5. Export: combine base layers + new layers + config, tag it hello-docker:v1
6. Load into the local image store, so docker run can find it
"""