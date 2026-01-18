# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Tests for port validation and SSH tunnel functionality."""

import pytest

from agentbox.config import validate_host_port, parse_port_spec


class TestPortValidation:
    """Tests for port validation functions."""

    def test_validate_host_port_privileged(self):
        """Should reject privileged ports."""
        with pytest.raises(ValueError) as exc_info:
            validate_host_port(80)
        assert "1024" in str(exc_info.value)
        assert "root" in str(exc_info.value).lower()

    def test_validate_host_port_zero(self):
        """Should reject port 0."""
        with pytest.raises(ValueError):
            validate_host_port(0)

    def test_validate_host_port_negative(self):
        """Should reject negative ports."""
        with pytest.raises(ValueError):
            validate_host_port(-1)

    def test_validate_host_port_too_high(self):
        """Should reject ports above 65535."""
        with pytest.raises(ValueError) as exc_info:
            validate_host_port(70000)
        assert "65535" in str(exc_info.value)

    def test_validate_host_port_valid_min(self):
        """Should accept port 1024 (minimum valid)."""
        validate_host_port(1024)  # Should not raise

    def test_validate_host_port_valid_max(self):
        """Should accept port 65535 (maximum valid)."""
        validate_host_port(65535)  # Should not raise

    def test_validate_host_port_common(self):
        """Should accept common non-privileged ports."""
        validate_host_port(3000)  # Common dev port
        validate_host_port(8080)  # Common HTTP alt port
        validate_host_port(9100)  # MCP port


class TestPortSpecParsing:
    """Tests for port specification parsing."""

    def test_parse_simple_port(self):
        """Should parse single port number."""
        result = parse_port_spec("3000")
        assert result["host_port"] == 3000
        assert result["container_port"] == 3000

    def test_parse_mapped_port(self):
        """Should parse host:container format."""
        result = parse_port_spec("8080:3000")
        assert result["host_port"] == 8080
        assert result["container_port"] == 3000

    def test_parse_invalid_format(self):
        """Should reject invalid formats."""
        with pytest.raises(ValueError) as exc_info:
            parse_port_spec("8080:3000:1234")
        assert "Invalid port format" in str(exc_info.value)

    def test_parse_invalid_number(self):
        """Should reject non-numeric values."""
        with pytest.raises(ValueError):
            parse_port_spec("abc")

    def test_parse_same_ports(self):
        """Should handle same port on both sides."""
        result = parse_port_spec("9100:9100")
        assert result["host_port"] == 9100
        assert result["container_port"] == 9100
