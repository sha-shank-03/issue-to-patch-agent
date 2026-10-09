package fixture;

/** Authored fictional semantic-defect fixture. */
public final class ShopApi {
    private int stockA = 5, stockB = 1, orders = 0, audit = 0;
    public int stockA() { return stockA; }
    public int stockB() { return stockB; }
    public int orders() { return orders; }
    public int audit() { return audit; }
    public void createOrder(int a, int b) {
        if (a <= 0 || b <= 0) throw new IllegalArgumentException("positive quantities required");
        if (stockA < a) throw new IllegalArgumentException("A unavailable");
        stockA -= a;
        if (stockB < b) throw new IllegalArgumentException("B unavailable");
        stockB -= b; orders++; audit++;
    }
}
