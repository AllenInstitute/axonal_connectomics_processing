FROM continuumio/miniconda3:23.10.0-1 as acpreprocessing

RUN conda update -y conda && conda install python=3.10 && conda clean -a

# Install bash if missing (usually is included, but safe)
RUN apt-get update && apt-get install -y curl bash && rm -rf /var/lib/apt/lists/*

# Install Pixi (curl installer)
RUN curl -fsSL https://pixi.sh/install.sh | bash

# Add Pixi to PATH for all RUN commands after this
ENV PATH="/root/.pixi/bin:${PATH}"

SHELL ["/bin/bash", "-c"]

COPY . /ac_deploy
ENTRYPOINT ["/bin/bash", "/ac_deploy/scripts/entrypoint.sh"]

WORKDIR /ac_deploy/repos/axonal_connectomics

RUN conda create -n ac --clone root && \
    source activate ac && \
    conda install -y pip && \
    conda install -y -c conda-forge gcc && \
    pip install . && \
    conda clean -a

WORKDIR /

FROM acpreprocessing as ac_analysis_preprocessing

WORKDIR /ac_deploy/repos/ac_reconstruction_analysis

RUN source activate ac && \
    pip install . && \
    conda clean -a

WORKDIR /

FROM ac_analysis_preprocessing as axconn

WORKDIR /ac_deploy/repos/ac_segmentation

RUN source activate ac && \
    pip install . && \
    conda clean -a

WORKDIR /
