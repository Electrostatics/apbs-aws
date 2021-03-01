# stage 1 - setup PDB2PQR binaries
FROM ubuntu:18.04 as pdb2pqr-build

WORKDIR /app
RUN apt update -y \
    # && apt install -y wget \
    # && wget https://github.com/Electrostatics/apbs-pdb2pqr/releases/download/pdb2pqr-2.1.1_release/pdb2pqr-linux-bin64-2.1.1.tar.gz \
    # && gunzip pdb2pqr-linux-bin64-2.1.1.tar.gz \
    # && tar -xf pdb2pqr-linux-bin64-2.1.1.tar \
    # download/clone necessary files
    && apt install -y python-pip swig g++ make git wget \
    && pip install numpy networkx

COPY pdb2pqr_build_materials/main.py .
COPY pdb2pqr_build_materials/build_config.py .

RUN git clone https://github.com/Electrostatics/apbs-pdb2pqr.git \
    # Download and unpack CMake
    && mkdir /app/misc \
    && cd /app/misc \
    && wget https://github.com/Kitware/CMake/releases/download/v3.15.4/cmake-3.15.4-Linux-x86_64.tar.gz \
    && gunzip cmake-3.15.4-Linux-x86_64.tar.gz \
    && tar -xf cmake-3.15.4-Linux-x86_64.tar \
    && export PATH=$PATH:/app/misc/cmake-3.15.4-Linux-x86_64/bin \
    # Checkout commit before PDB2PQR v3.0 changes
    && cd /app/apbs-pdb2pqr \
    && git checkout b3bfeec \
    # Install APBS
    && cd /app/apbs-pdb2pqr/apbs \
    && git submodule init \
    && git submodule update \
    && mkdir -p /app/builds/apbs \
    && cd /app/builds/apbs \
    && cmake /app/apbs-pdb2pqr/apbs/ -DENABLE_PYTHON=ON -DBUILD_SHARED_LIBS=ON \
    && make \
    # Move custom files into repo; install PDB2PQR
    && cd /app \
    && mv main.py build_config.py /app/apbs-pdb2pqr/pdb2pqr/. \
    && cd /app/apbs-pdb2pqr/pdb2pqr \
    && python scons/scons.py \
    && python scons/scons.py install
RUN mkdir /app/run \
    && cd /app/run \
    # Cleanup
    # && rm pdb2pqr-linux-bin64-2.1.1.tar \
    # && rm -r /app/apbs-pdb2pqr \
    && apt autoremove -y \
    && apt clean -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/run

# Copy builds to cleaner base
FROM ubuntu:18.04 as pdb2pqr-final
COPY --from=pdb2pqr-build /app/builds /app/builds
RUN apt update \
    && apt install python python-setuptools wget zip libpython2.7 libmaloc-dev -y \
    # Install networkx for PDB2PKA
    && wget https://files.pythonhosted.org/packages/f3/f4/7e20ef40b118478191cec0b58c3192f822cace858c19505c7670961b76b2/networkx-2.2.zip \
    && unzip networkx-2.2.zip \
    && cd networkx-2.2 \
    && python setup.py install \
    # Cleanup and remove unneeded packages
    && rm -r /networkx-2.2 /networkx-2.2.zip \
    && apt remove zip wget -y \
    && apt autoremove -y \
    && apt clean -y
    
WORKDIR /app/run

ENTRYPOINT [ "/app/builds/pdb2pqr/pdb2pqr.py" ]
# ENTRYPOINT [ "python pdb2pqr.py" ]
# ENTRYPOINT [ "bash" ]