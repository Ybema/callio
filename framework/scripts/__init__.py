"""
project framework Core Components

This package contains the core components of the generic proposal support framework.
"""

from .framework import ProposalFramework
from .document_processor import DocumentProcessor
# from .review_engine import ReviewEngine  # Commented out - class doesn't exist
from .version_control import VersionControl
from .output_generator import OutputGenerator

__all__ = [
    'ProposalFramework',
    'DocumentProcessor', 
    # 'ReviewEngine',  # Commented out - class doesn't exist
    'VersionControl',
    'OutputGenerator'
]
