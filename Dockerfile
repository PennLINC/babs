FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    bzip2 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


# Create a shared $HOME directory
RUN useradd -m -s /bin/bash -G users babs
WORKDIR /home/babs
ENV HOME="/home/babs"

WORKDIR /
RUN echo "2024.04.11"
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba

COPY docker/environment.yml /tmp/environment.yml
ENV MAMBA_ROOT_PREFIX="/opt/conda" \
    MAMBA_NO_LOW_SPEED_LIMIT=1 \
    PIP_DEFAULT_TIMEOUT=100

RUN micromamba config set extract_threads 1 \
    && micromamba create -vv -y -f /tmp/environment.yml \
    && micromamba clean -y -a

ENV PATH=/opt/conda/envs/babs/bin:$PATH

# Configure the git user name and email
RUN git config --global user.name "CircleCI" \
    && git config --global user.email "circleci@example.com"

# Create toy bids app
RUN mkdir -p /singularity_images \
    && apptainer build \
    /singularity_images/toybidsapp_0.0.7.sif \
    docker://pennlinc/toy_bids_app:0.0.7

# # install BABS
# COPY . $HOME/babs
# WORKDIR $HOME/babs
# RUN pip install .[tests]

# # pytest BABS
# RUN pytest ~/babs