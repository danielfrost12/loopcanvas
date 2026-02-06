#!/usr/bin/env python3
"""
Canvas Cost Enforcer — $0 Until Revenue

HARD RULE: No money spent until money is made.

This module enforces the zero-cost constraint across all Canvas operations.
It blocks any action that would incur cost until revenue threshold is met.

The $0 Rule:
1. All compute must use free tiers or startup credits
2. All models must be self-hosted or free API
3. Any paid API call is BLOCKED until revenue > $0
4. Alert on ANY spend attempt
"""

import os
import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path


@dataclass
class CostEvent:
    """A record of a cost-incurring event"""
    timestamp: str
    service: str
    action: str
    estimated_cost: float
    blocked: bool
    reason: str


@dataclass
class RevenueStatus:
    """Current revenue status"""
    total_revenue: float
    last_updated: str
    revenue_source: str  # "stripe", "manual", etc.


class CostEnforcer:
    """
    The Cost Enforcer - Ensures $0 spend until revenue.

    Usage:
        enforcer = CostEnforcer()

        # Check before any potentially costly operation
        if enforcer.can_spend(service="modal", estimated_cost=0.10):
            # Proceed with operation
            pass
        else:
            # Use free alternative
            pass

        # Or use decorator
        @enforcer.enforce_zero_cost
        def expensive_operation():
            pass
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._default_config_path()
        self.config = self._load_config()
        self.events: List[CostEvent] = []
        self.revenue = self._load_revenue()

        # Alert handlers
        self.alert_handlers: List[Callable] = []

        # Free tier limits (tracked to avoid surprise charges)
        self.free_tier_usage = {
            'vercel': {'used': 0, 'limit': 100},  # GB bandwidth
            'supabase': {'used': 0, 'limit': 500},  # MB storage
            'clerk': {'used': 0, 'limit': 10000},  # MAU
            'resend': {'used': 0, 'limit': 3000},  # emails/month
        }

    def _default_config_path(self) -> str:
        return str(Path(__file__).parent.parent / "agent-config.yaml")

    def _load_config(self) -> dict:
        """Load cost enforcement config"""
        default_config = {
            'cost_ceiling': 0.0,
            'alert_threshold': 0.01,
            'hard_block': True,
            'allowed_paid_apis': [],
            'revenue_threshold': 0.01,  # Minimum revenue to unlock spending
        }

        if os.path.exists(self.config_path):
            try:
                import yaml
                with open(self.config_path) as f:
                    full_config = yaml.safe_load(f)
                    return full_config.get('cost_enforcement', default_config)
            except:
                pass

        return default_config

    def _load_revenue(self) -> RevenueStatus:
        """Load current revenue status"""
        # In production, this would check Stripe API
        # For now, check local file
        revenue_file = Path(__file__).parent / ".revenue_status.json"

        if revenue_file.exists():
            try:
                with open(revenue_file) as f:
                    data = json.load(f)
                    return RevenueStatus(**data)
            except:
                pass

        return RevenueStatus(
            total_revenue=0.0,
            last_updated=datetime.now().isoformat(),
            revenue_source="none"
        )

    def update_revenue(self, amount: float, source: str = "stripe"):
        """Update revenue status (called by billing system)"""
        self.revenue.total_revenue += amount
        self.revenue.last_updated = datetime.now().isoformat()
        self.revenue.revenue_source = source

        # Save to file
        revenue_file = Path(__file__).parent / ".revenue_status.json"
        with open(revenue_file, 'w') as f:
            json.dump({
                'total_revenue': self.revenue.total_revenue,
                'last_updated': self.revenue.last_updated,
                'revenue_source': self.revenue.revenue_source
            }, f)

        print(f"[CostEnforcer] Revenue updated: ${self.revenue.total_revenue:.2f}")

    def has_revenue(self) -> bool:
        """Check if we have any revenue"""
        return self.revenue.total_revenue >= self.config.get('revenue_threshold', 0.01)

    def can_spend(self, service: str, estimated_cost: float,
                  action: str = "unknown") -> bool:
        """
        Check if a cost-incurring action is allowed.

        Returns True only if:
        1. We have revenue > $0, OR
        2. The service is in allowed_paid_apis, OR
        3. We're using startup credits

        Otherwise, returns False and logs the blocked action.
        """
        # Always allow if we have revenue
        if self.has_revenue():
            self._log_event(service, action, estimated_cost, blocked=False,
                           reason="Revenue threshold met")
            return True

        # Check if service is explicitly allowed
        allowed = self.config.get('allowed_paid_apis', [])
        if service in allowed:
            self._log_event(service, action, estimated_cost, blocked=False,
                           reason=f"Service {service} is in allowed list")
            return True

        # Check for $0 cost (free tier)
        if estimated_cost <= 0:
            return True

        # BLOCK - No revenue, not allowed
        self._log_event(service, action, estimated_cost, blocked=True,
                       reason="No revenue - $0 rule enforced")
        self._alert(f"BLOCKED: {service} would cost ${estimated_cost:.4f}")

        return False

    def get_free_alternative(self, service: str) -> Optional[str]:
        """Suggest a free alternative to a paid service"""
        alternatives = {
            'openai': 'llama-3.1-8b (self-hosted)',
            'anthropic': 'llama-3.1-8b (self-hosted)',
            'claude': 'llama-3.1-8b (self-hosted)',
            'gpt-4': 'llama-3.1-8b (self-hosted)',
            'dalle': 'stable-diffusion (self-hosted)',
            'midjourney': 'stable-diffusion (self-hosted)',
            'replicate': 'modal (free credits) or huggingface',
            'runway': 'stable-video-diffusion (self-hosted)',
            'aws_lambda': 'vercel (free tier)',
            'aws_s3': 'supabase storage (free tier)',
            'firebase': 'supabase (free tier)',
            'auth0': 'clerk (free tier)',
            'sendgrid': 'resend (free tier)',
            'twilio': 'resend (free tier)',
        }
        return alternatives.get(service.lower())

    def track_free_tier_usage(self, service: str, amount: float):
        """Track usage of free tiers to avoid surprise charges"""
        if service in self.free_tier_usage:
            self.free_tier_usage[service]['used'] += amount
            usage = self.free_tier_usage[service]

            # Alert at 80% usage
            if usage['used'] / usage['limit'] > 0.8:
                self._alert(
                    f"WARNING: {service} at {usage['used']}/{usage['limit']} "
                    f"({100*usage['used']/usage['limit']:.0f}% of free tier)"
                )

    def enforce_zero_cost(self, func: Callable) -> Callable:
        """Decorator to enforce zero cost on a function"""
        def wrapper(*args, **kwargs):
            service = kwargs.get('service', func.__name__)
            cost = kwargs.get('estimated_cost', 0.01)  # Assume some cost

            if not self.can_spend(service, cost, action=func.__name__):
                alt = self.get_free_alternative(service)
                raise CostBlockedError(
                    f"Action blocked by $0 rule. "
                    f"Alternative: {alt or 'Use free tier'}"
                )

            return func(*args, **kwargs)
        return wrapper

    def _log_event(self, service: str, action: str, cost: float,
                   blocked: bool, reason: str):
        """Log a cost event"""
        event = CostEvent(
            timestamp=datetime.now().isoformat(),
            service=service,
            action=action,
            estimated_cost=cost,
            blocked=blocked,
            reason=reason
        )
        self.events.append(event)

        # Keep only last 1000 events
        if len(self.events) > 1000:
            self.events = self.events[-1000:]

    def _alert(self, message: str):
        """Send alert about cost issue"""
        print(f"[COST ALERT] {message}")

        # Call registered handlers
        for handler in self.alert_handlers:
            try:
                handler(message)
            except:
                pass

    def add_alert_handler(self, handler: Callable):
        """Add a handler for cost alerts"""
        self.alert_handlers.append(handler)

    def get_status(self) -> dict:
        """Get current cost enforcement status"""
        recent_blocked = [e for e in self.events[-100:] if e.blocked]

        return {
            'revenue': self.revenue.total_revenue,
            'has_revenue': self.has_revenue(),
            'cost_ceiling': self.config.get('cost_ceiling', 0),
            'hard_block_enabled': self.config.get('hard_block', True),
            'allowed_services': self.config.get('allowed_paid_apis', []),
            'recent_blocked_count': len(recent_blocked),
            'free_tier_usage': self.free_tier_usage,
        }

    def report(self) -> str:
        """Generate a cost enforcement report"""
        status = self.get_status()

        lines = [
            "=" * 50,
            "CANVAS COST ENFORCEMENT REPORT",
            "=" * 50,
            f"Revenue: ${status['revenue']:.2f}",
            f"Spending Unlocked: {'YES' if status['has_revenue'] else 'NO'}",
            f"Hard Block: {'ENABLED' if status['hard_block_enabled'] else 'DISABLED'}",
            "",
            "Free Tier Usage:",
        ]

        for service, usage in status['free_tier_usage'].items():
            pct = 100 * usage['used'] / usage['limit']
            lines.append(f"  {service}: {usage['used']}/{usage['limit']} ({pct:.0f}%)")

        if status['recent_blocked_count'] > 0:
            lines.append("")
            lines.append(f"Blocked Actions (last 100): {status['recent_blocked_count']}")

        return "\n".join(lines)


class CostBlockedError(Exception):
    """Raised when an action is blocked by cost enforcement"""
    pass


# Singleton instance
_enforcer = None


def get_enforcer() -> CostEnforcer:
    """Get the global cost enforcer instance"""
    global _enforcer
    if _enforcer is None:
        _enforcer = CostEnforcer()
    return _enforcer


# Convenience functions
def can_spend(service: str, estimated_cost: float) -> bool:
    return get_enforcer().can_spend(service, estimated_cost)


def get_free_alternative(service: str) -> Optional[str]:
    return get_enforcer().get_free_alternative(service)


def enforce_zero_cost(func: Callable) -> Callable:
    return get_enforcer().enforce_zero_cost(func)


# CLI
if __name__ == "__main__":
    enforcer = CostEnforcer()
    print(enforcer.report())

    print("\n" + "=" * 50)
    print("Testing cost checks:")

    # Test some services
    tests = [
        ("openai", 0.05, "gpt-4 call"),
        ("modal", 0.00, "free credits"),
        ("vercel", 0.00, "free tier"),
        ("replicate", 0.10, "video generation"),
    ]

    for service, cost, action in tests:
        allowed = enforcer.can_spend(service, cost, action)
        alt = enforcer.get_free_alternative(service)
        print(f"\n{service} (${cost:.2f}): {'ALLOWED' if allowed else 'BLOCKED'}")
        if not allowed and alt:
            print(f"  → Alternative: {alt}")
