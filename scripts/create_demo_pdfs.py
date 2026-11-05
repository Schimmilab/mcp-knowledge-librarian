#!/usr/bin/env python3
"""Create demo PDF files for testing."""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


def create_demo_library():
    """Create a demo library with sample PDFs."""
    demo_dir = Path("demo_library")
    demo_dir.mkdir(exist_ok=True)

    # Document 1: Machine Learning Guide
    create_ml_guide(demo_dir / "machine_learning_guide.pdf")

    # Document 2: Data Science Introduction
    create_data_science_intro(demo_dir / "data_science_intro.pdf")

    # Document 3: Python for Beginners
    create_python_guide(demo_dir / "python_beginners.pdf")

    # Document 4: Neural Networks Deep Dive
    create_neural_networks_guide(demo_dir / "neural_networks.pdf")

    # Document 5: Statistics Fundamentals
    create_statistics_guide(demo_dir / "statistics_fundamentals.pdf")

    print(f"Created 5 demo PDFs in {demo_dir}")


def create_ml_guide(path: Path):
    """Create machine learning guide PDF."""
    c = canvas.Canvas(str(path), pagesize=letter)

    # Page 1
    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, 750, "Machine Learning Guide")
    c.setFont("Helvetica", 12)
    c.drawString(100, 720, "A Comprehensive Introduction")

    y = 680
    lines = [
        "",
        "Chapter 1: Introduction to Machine Learning",
        "",
        "Machine learning is a subset of artificial intelligence that enables",
        "computers to learn from data without being explicitly programmed.",
        "It focuses on developing algorithms that can identify patterns and",
        "make predictions based on training data.",
        "",
        "Key concepts in machine learning include:",
        "  - Supervised learning: learning from labeled data",
        "  - Unsupervised learning: finding patterns in unlabeled data",
        "  - Reinforcement learning: learning through trial and error",
        "",
        "Applications of machine learning are widespread, including:",
        "  - Image and speech recognition",
        "  - Natural language processing",
        "  - Recommendation systems",
        "  - Predictive analytics",
    ]

    for line in lines:
        c.drawString(100, y, line)
        y -= 20

    # Page 2
    c.showPage()
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Chapter 2: Neural Networks")
    c.setFont("Helvetica", 12)

    y = 720
    lines = [
        "",
        "Neural networks are computational models inspired by biological",
        "neurons in the human brain. They consist of interconnected nodes",
        "organized in layers that process and transform input data.",
        "",
        "A typical neural network includes:",
        "  - Input layer: receives raw data",
        "  - Hidden layers: process and extract features",
        "  - Output layer: produces predictions",
        "",
        "Deep learning refers to neural networks with multiple hidden layers,",
        "enabling them to learn complex hierarchical representations.",
        "",
        "Popular architectures include:",
        "  - Convolutional Neural Networks (CNNs) for image processing",
        "  - Recurrent Neural Networks (RNNs) for sequential data",
        "  - Transformers for natural language processing",
    ]

    for line in lines:
        c.drawString(100, y, line)
        y -= 20

    c.save()


def create_data_science_intro(path: Path):
    """Create data science introduction PDF."""
    c = canvas.Canvas(str(path), pagesize=letter)

    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, 750, "Introduction to Data Science")
    c.setFont("Helvetica", 12)

    y = 700
    lines = [
        "",
        "Data science is an interdisciplinary field that combines statistics,",
        "computer science, and domain expertise to extract insights from data.",
        "",
        "The data science workflow typically includes:",
        "  1. Data collection and cleaning",
        "  2. Exploratory data analysis",
        "  3. Feature engineering",
        "  4. Model building and validation",
        "  5. Deployment and monitoring",
        "",
        "Essential skills for data scientists:",
        "  - Programming (Python, R, SQL)",
        "  - Statistics and probability",
        "  - Machine learning algorithms",
        "  - Data visualization",
        "  - Domain knowledge",
        "",
        "Common tools and libraries:",
        "  - pandas for data manipulation",
        "  - NumPy for numerical computing",
        "  - scikit-learn for machine learning",
        "  - matplotlib and seaborn for visualization",
    ]

    for line in lines:
        c.drawString(100, y, line)
        y -= 20

    c.save()


def create_python_guide(path: Path):
    """Create Python beginners guide PDF."""
    c = canvas.Canvas(str(path), pagesize=letter)

    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, 750, "Python for Beginners")
    c.setFont("Helvetica", 12)

    y = 700
    lines = [
        "",
        "Python is a high-level, interpreted programming language known",
        "for its simplicity and readability. It is widely used in:",
        "  - Web development",
        "  - Data science and machine learning",
        "  - Automation and scripting",
        "  - Scientific computing",
        "",
        "Basic Python syntax:",
        "",
        "Variables and data types:",
        "  x = 42          # integer",
        "  name = 'Alice'  # string",
        "  data = [1,2,3]  # list",
        "",
        "Control flow:",
        "  if x > 0:",
        "      print('positive')",
        "  else:",
        "      print('non-positive')",
        "",
        "Functions:",
        "  def greet(name):",
        "      return f'Hello, {name}!'",
    ]

    for line in lines:
        c.drawString(100, y, line)
        y -= 20

    c.save()


def create_neural_networks_guide(path: Path):
    """Create neural networks deep dive PDF."""
    c = canvas.Canvas(str(path), pagesize=letter)

    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, 750, "Neural Networks: A Deep Dive")
    c.setFont("Helvetica", 12)

    y = 700
    lines = [
        "",
        "Deep neural networks have revolutionized artificial intelligence,",
        "achieving breakthrough results in computer vision, natural language",
        "processing, and game playing.",
        "",
        "Training neural networks:",
        "  1. Forward propagation: compute predictions",
        "  2. Loss calculation: measure prediction error",
        "  3. Backpropagation: compute gradients",
        "  4. Weight updates: adjust parameters using optimization",
        "",
        "Activation functions:",
        "  - ReLU (Rectified Linear Unit): most common for hidden layers",
        "  - Sigmoid: outputs between 0 and 1",
        "  - Softmax: for multi-class classification",
        "",
        "Optimization algorithms:",
        "  - Stochastic Gradient Descent (SGD)",
        "  - Adam: adaptive learning rate method",
        "  - RMSprop: for recurrent neural networks",
    ]

    for line in lines:
        c.drawString(100, y, line)
        y -= 20

    c.save()


def create_statistics_guide(path: Path):
    """Create statistics fundamentals PDF."""
    c = canvas.Canvas(str(path), pagesize=letter)

    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, 750, "Statistics Fundamentals")
    c.setFont("Helvetica", 12)

    y = 700
    lines = [
        "",
        "Statistics is the science of collecting, analyzing, and interpreting",
        "data. It provides the mathematical foundation for data science.",
        "",
        "Descriptive statistics:",
        "  - Mean: average value",
        "  - Median: middle value",
        "  - Standard deviation: measure of spread",
        "  - Correlation: relationship between variables",
        "",
        "Probability distributions:",
        "  - Normal distribution: bell curve",
        "  - Binomial distribution: success/failure trials",
        "  - Poisson distribution: event counts",
        "",
        "Hypothesis testing:",
        "  - Null hypothesis: no effect exists",
        "  - Alternative hypothesis: effect exists",
        "  - P-value: probability of observing results by chance",
        "  - Significance level: threshold for rejecting null hypothesis",
    ]

    for line in lines:
        c.drawString(100, y, line)
        y -= 20

    c.save()


if __name__ == "__main__":
    create_demo_library()
