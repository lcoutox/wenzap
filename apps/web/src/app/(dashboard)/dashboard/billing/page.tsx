"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Alert from "@/components/ui/Alert";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

interface Plan {
  id: string;
  name: string;
  description: string;
  monthly_price_cents: number;
  features: string[];
}

interface WorkspaceSubscription {
  id: string;
  plan_id: string;
  status: "active" | "cancelling" | "inactive";
  period_start: string;
  period_end: string;
  stripe_subscription_id: string | null;
  cancel_at_period_end: boolean;
}

export default function BillingPage() {
  const searchParams = useSearchParams();
  const { workspace, currentUser } = useWorkspace();
  const [subscription, setSubscription] = useState<WorkspaceSubscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [couponCode, setCouponCode] = useState("");
  const [couponError, setCouponError] = useState("");
  const [couponValid, setCouponValid] = useState(false);
  const [couponDiscount, setCouponDiscount] = useState<any>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Show success message if redirected from successful checkout
  useEffect(() => {
    if (searchParams.get("success") === "true") {
      setSuccess("Pagamento realizado com sucesso! Seu plano foi atualizado.");
      const timer = setTimeout(() => setSuccess(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [searchParams]);

  // Fetch subscription and plans
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [subRes, plansRes] = await Promise.all([
          fetch(`/api/workspaces/${workspace.id}/billing/subscription`),
          fetch("/api/billing/plans"),
        ]);

        if (!subRes.ok || !plansRes.ok) {
          throw new Error("Failed to fetch billing data");
        }

        const subscriptionData = await subRes.json();
        const plansData = await plansRes.json();

        setSubscription(subscriptionData);
        setPlans(plansData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load billing data");
      } finally {
        setLoading(false);
      }
    };

    if (workspace?.id) {
      fetchData();
    }
  }, [workspace?.id]);

  const validateCoupon = async (code: string, planId: string) => {
    if (!code.trim()) {
      setCouponError("");
      setCouponValid(false);
      setCouponDiscount(null);
      return;
    }

    try {
      const response = await fetch(
        `/api/workspaces/${workspace.id}/billing/validate-coupon`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ coupon_code: code, plan_id: planId }),
        }
      );

      const result = await response.json();

      if (result.valid) {
        setCouponValid(true);
        setCouponError("");
        setCouponDiscount(result);
      } else {
        setCouponValid(false);
        setCouponError(result.error || "Cupom inválido");
        setCouponDiscount(null);
      }
    } catch (err) {
      setCouponValid(false);
      setCouponError("Erro ao validar cupom");
      setCouponDiscount(null);
    }
  };

  const handleUpgrade = async (planId: string) => {
    setCheckoutLoading(true);
    try {
      const response = await fetch(
        `/api/workspaces/${workspace.id}/billing/checkout-session`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            plan_id: planId,
            coupon_code: couponValid ? couponCode : undefined,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to create checkout session");
      }

      const { checkout_url } = await response.json();
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create checkout");
    } finally {
      setCheckoutLoading(false);
    }
  };

  const handleManageSubscription = async () => {
    try {
      const response = await fetch(
        `/api/workspaces/${workspace.id}/billing/portal-session`
      );

      if (!response.ok) {
        throw new Error("Failed to create portal session");
      }

      const { portal_url } = await response.json();
      window.location.href = portal_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open portal");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner />
      </div>
    );
  }

  const currentPlan = subscription && plans.find(p => p.id === subscription.plan_id);

  return (
    <div className="space-y-8 max-w-7xl mx-auto p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">Faturamento</h1>
        <p className="text-gray-600">Gerencie sua assinatura e método de pagamento</p>
      </div>

      {/* Alerts */}
      {success && <Alert type="success" message={success} />}
      {error && <Alert type="error" message={error} />}

      {/* Current Plan */}
      {subscription && (
        <Card className="p-6 border-l-4 border-blue-500">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-xl font-semibold mb-1">Plano Atual</h2>
              <p className="text-gray-600 mb-4">{currentPlan?.name}</p>

              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-gray-600">Status:</span>{" "}
                  <span
                    className={`font-semibold ${
                      subscription.status === "active"
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {subscription.status === "active"
                      ? "Ativo"
                      : subscription.status === "cancelling"
                      ? "Cancelando no final do período"
                      : "Inativo"}
                  </span>
                </p>

                <p>
                  <span className="text-gray-600">Período:</span>{" "}
                  <span className="font-semibold">
                    {new Date(subscription.period_start).toLocaleDateString("pt-BR")}{" "}
                    -{" "}
                    {new Date(subscription.period_end).toLocaleDateString("pt-BR")}
                  </span>
                </p>

                {subscription.cancel_at_period_end && (
                  <p className="text-orange-600 font-semibold">
                    ⚠️ Sua assinatura será cancelada ao final deste período
                  </p>
                )}
              </div>
            </div>

            <Button
              onClick={handleManageSubscription}
              variant="outline"
            >
              Gerenciar Assinatura
            </Button>
          </div>
        </Card>
      )}

      {/* Plans Grid */}
      <div>
        <h2 className="text-2xl font-bold mb-6">Planos Disponíveis</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {plans.map(plan => {
            const isCurrentPlan = subscription?.plan_id === plan.id;
            const price = plan.monthly_price_cents / 100;

            return (
              <Card
                key={plan.id}
                className={`p-6 flex flex-col ${
                  isCurrentPlan ? "border-2 border-blue-500" : ""
                }`}
              >
                {isCurrentPlan && (
                  <div className="mb-4 px-3 py-1 bg-blue-100 text-blue-700 text-sm font-semibold rounded-full w-fit">
                    Plano Atual
                  </div>
                )}

                <h3 className="text-xl font-semibold mb-2">{plan.name}</h3>
                <p className="text-gray-600 text-sm mb-4">{plan.description}</p>

                <div className="mb-6">
                  <span className="text-4xl font-bold">
                    R${price.toFixed(2)}
                  </span>
                  <span className="text-gray-600">/mês</span>
                </div>

                <div className="flex-1">
                  <h4 className="font-semibold text-sm mb-3">Incluso:</h4>
                  <ul className="space-y-2">
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="text-sm flex items-start">
                        <span className="text-green-600 mr-2">✓</span>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>

                {!isCurrentPlan && (
                  <Button
                    onClick={() => handleUpgrade(plan.id)}
                    loading={checkoutLoading}
                    className="w-full mt-6"
                  >
                    Fazer Upgrade
                  </Button>
                )}
              </Card>
            );
          })}
        </div>
      </div>

      {/* Coupon Section */}
      {subscription?.status === "active" && !subscription.cancel_at_period_end && (
        <Card className="p-6 bg-gray-50">
          <h3 className="text-lg font-semibold mb-4">Aplicar Cupom de Desconto</h3>

          <div className="flex gap-3 mb-4">
            <input
              type="text"
              placeholder="Código do cupom"
              value={couponCode}
              onChange={e => {
                setCouponCode(e.target.value);
                if (subscription) {
                  validateCoupon(e.target.value, subscription.plan_id);
                }
              }}
              className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {couponError && (
            <p className="text-red-600 text-sm mb-2">{couponError}</p>
          )}

          {couponValid && couponDiscount && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm">
              <p className="font-semibold text-green-700 mb-2">Cupom válido! 🎉</p>
              <p className="text-green-600">
                Desconto de{" "}
                {couponDiscount.discount_type === "percent"
                  ? `${couponDiscount.discount_value}%`
                  : `R$${(couponDiscount.discount_value).toFixed(2)}`}
              </p>
              <p className="text-green-600 text-xs mt-1">
                Preço original: R${(couponDiscount.original_price_cents / 100).toFixed(2)}
                <br />
                Preço com desconto: R${(couponDiscount.discounted_price_cents / 100).toFixed(2)}
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Billing History */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Histórico de Faturas</h3>
        <p className="text-gray-600 text-sm">
          Você pode visualizar e baixar suas faturas no portal de faturamento do Stripe.
        </p>
        <Button
          onClick={handleManageSubscription}
          variant="outline"
          className="mt-4"
        >
          Acessar Portal de Faturamento
        </Button>
      </Card>
    </div>
  );
}
