package fixture;

/** Authored observations, no expected outcomes. */
public final class IndependentProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(2147483647, 2); } catch (RuntimeException rejected) { ok = false; }
          out("overflow_negative", "accepted", "bool", Boolean.toString(ok));
          out("overflow_negative", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(0, 3); } catch (RuntimeException rejected) { ok = false; }
          out("first", "accepted", "bool", Boolean.toString(ok));
          out("first", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(0, 0); } catch (RuntimeException rejected) { ok = false; }
          out("bad_size", "accepted", "bool", Boolean.toString(ok));
          out("bad_size", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(1073741824, 4); } catch (RuntimeException rejected) { ok = false; }
          out("overflow_zero", "accepted", "bool", Boolean.toString(ok));
          out("overflow_zero", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(1, 4); } catch (RuntimeException rejected) { ok = false; }
          out("short_final", "accepted", "bool", Boolean.toString(ok));
          out("short_final", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(4, 2); } catch (RuntimeException rejected) { ok = false; }
          out("past_end", "accepted", "bool", Boolean.toString(ok));
          out("past_end", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(-1, 2); } catch (RuntimeException rejected) { ok = false; }
          out("negative_page", "accepted", "bool", Boolean.toString(ok));
          out("negative_page", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
    }
}
