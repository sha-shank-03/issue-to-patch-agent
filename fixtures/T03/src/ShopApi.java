package fixture;

/** Authored fictional semantic-defect fixture. */
public final class ShopApi {
    private int stockA = 5, stockB = 8, orders = 0, audit = 0;
    public int stockA() { return stockA; }
    public int stockB() { return stockB; }
    public int orders() { return orders; }
    public int audit() { return audit; }
    public void createOrder(int quantity, boolean failAudit) {
        if (quantity <= 0 || quantity > stockA) throw new IllegalArgumentException("invalid quantity");
        stockA -= quantity; orders++;
        if (failAudit) throw new IllegalArgumentException("injected audit failure");
        audit++;
    }
}
