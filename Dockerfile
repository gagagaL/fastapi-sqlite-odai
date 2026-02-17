FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    mecab \
    libmecab-dev \
    mecab-ipadic \
    mecab-ipadic-utf8 \
    swig \
    build-essential \
    python3-pip \
    git \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Rust for SudachiPy
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Configure MeCab
ENV MECABRC /etc/mecabrc
RUN echo "dicdir = /var/lib/mecab/dic/ipadic-utf8" > /etc/mecabrc

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt && \
    python -c "import sudachipy; print('SudachiPy installed successfully')" && \
    python -c "import janome; print('Janome installed successfully')"

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data && chmod -R 777 /app/data

RUN mecab-config --dicdir

# Verify MeCab installation
RUN python3 -c "import MeCab; tagger = MeCab.Tagger(''); print(tagger.parse('テスト'))"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]