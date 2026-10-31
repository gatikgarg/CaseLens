"""Stub adapter signalling the extension point for Zendesk/Intercom/Salesforce.

To support a new source, implement ``TicketSourceAdapter`` and emit the same
canonical ``Batch`` objects (tickets / events / utterances) that the Mendeley
adapter emits. Nothing downstream of the adapter needs to change.
"""

