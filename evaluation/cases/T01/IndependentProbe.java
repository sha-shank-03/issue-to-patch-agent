package fixture;

/** Authored observations, no expected outcomes. */
public final class IndependentProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(2, 2); } catch (RuntimeException rejected) { ok = false; }
          out("second_failure", "accepted", "bool", Boolean.toString(ok));
          out("second_failure", "stockA", "int", Long.toString(api.stockA()));
          out("second_failure", "stockB", "int", Long.toString(api.stockB()));
          out("second_failure", "orders", "int", Long.toString(api.orders()));
          out("second_failure", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(1, 1); } catch (RuntimeException rejected) { ok = false; }
          out("success", "accepted", "bool", Boolean.toString(ok));
          out("success", "stockA", "int", Long.toString(api.stockA()));
          out("success", "stockB", "int", Long.toString(api.stockB()));
          out("success", "orders", "int", Long.toString(api.orders()));
          out("success", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(0, 1); } catch (RuntimeException rejected) { ok = false; }
          out("invalid", "accepted", "bool", Boolean.toString(ok));
          out("invalid", "stockA", "int", Long.toString(api.stockA()));
          out("invalid", "stockB", "int", Long.toString(api.stockB()));
          out("invalid", "orders", "int", Long.toString(api.orders()));
          out("invalid", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(3, 2); } catch (RuntimeException rejected) { ok = false; }
          out("unequal_failure", "accepted", "bool", Boolean.toString(ok));
          out("unequal_failure", "stockA", "int", Long.toString(api.stockA()));
          out("unequal_failure", "stockB", "int", Long.toString(api.stockB()));
          out("unequal_failure", "orders", "int", Long.toString(api.orders()));
          out("unequal_failure", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(6, 1); } catch (RuntimeException rejected) { ok = false; }
          out("first_failure", "accepted", "bool", Boolean.toString(ok));
          out("first_failure", "stockA", "int", Long.toString(api.stockA()));
          out("first_failure", "stockB", "int", Long.toString(api.stockB()));
          out("first_failure", "orders", "int", Long.toString(api.orders()));
          out("first_failure", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(5, 1); } catch (RuntimeException rejected) { ok = false; }
          out("boundary", "accepted", "bool", Boolean.toString(ok));
          out("boundary", "stockA", "int", Long.toString(api.stockA()));
          out("boundary", "stockB", "int", Long.toString(api.stockB()));
          out("boundary", "orders", "int", Long.toString(api.orders()));
          out("boundary", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(-1, 1); } catch (RuntimeException rejected) { ok = false; }
          out("negative", "accepted", "bool", Boolean.toString(ok));
          out("negative", "stockA", "int", Long.toString(api.stockA()));
          out("negative", "stockB", "int", Long.toString(api.stockB()));
          out("negative", "orders", "int", Long.toString(api.orders()));
          out("negative", "audit", "int", Long.toString(api.audit()));
        }
    }
}
