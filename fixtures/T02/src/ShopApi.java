package fixture;

/** Authored fictional semantic-defect fixture. */
public final class ShopApi {
    private int stockA = 5, stockB = 8, orders = 0, audit = 0;
    public int stockA() { return stockA; }
    public int stockB() { return stockB; }
    public int orders() { return orders; }
    public int audit() { return audit; }
    public void createOrder(int[] quantities) {
        int total = 0;
        for (int q : quantities) {
            if (q <= 0 || q > stockA) throw new IllegalArgumentException("invalid line");
            total += q;
        }
        stockA -= total; orders++; audit++;
    }
}
