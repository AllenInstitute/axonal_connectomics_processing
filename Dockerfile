FROM continuumio/miniconda3:23.10.0-1 as acpreprocessing
RUN conda update -y conda && conda install python=3.10 && conda clean -a

SHELL ["/bin/bash", "-c"]

COPY . /ac_deploy
ENTRYPOINT ["/bin/bash", "/ac_deploy/scripts/entrypoint.sh"]

# Initialize & update ALL submodules, WHEN REPOS ARE ALL PUBLIC
#WORKDIR /ac_deploy/repos
#RUN git submodule update --init --recursive

# === AXONAL_CONNECTOMICS ===
WORKDIR /ac_deploy/repos/axonal_connectomics
RUN conda create -n ac --clone root && \
  source activate ac && \
  conda install -y pip && \
  conda install -y -c conda-forge gcc && \
  pip install . && \
  conda clean -a

WORKDIR /

FROM acpreprocessing as ac_analysis_preprocessing

# === AC_RECONSTRUCTION_ANALYSIS ===
WORKDIR /ac_deploy/repos/ac_reconstruction_analysis
RUN source activate ac && \
  pip install . && \
  pytest && \
  conda clean -a

WORKDIR /

FROM ac_analysis_preprocessing as axconn

# === AC_SEGMENTATION ===
WORKDIR /ac_deploy/repos/ac_segmentation
RUN source activate ac && \
  pip install . && \
  pytest && \
  conda clean -a

WORKDIR /
