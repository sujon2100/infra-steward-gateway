"""
Supervisory / tax reporting service package.

Provides a simulated downstream that the workflow engine dispatches enriched
reports to after a successful AI provider invocation. In the prototype the
service simply counts and logs submissions; in a real deployment this would
forward the report to an external supervisory or tax-reporting endpoint.
"""
