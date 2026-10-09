package fixture;

/** Authored fictional API. One intentional quantity-validation defect. */
public final class ShopApi {
    private int stock = 200;
    private int orders = 0;

    public void createOrder(int quantity) {
        if (quantity < 0 || quantity > 100) {
            throw new IllegalArgumentException("quantity must be between 1 and 100");
        }
        stock -= quantity;
        orders++;
    }

    public int stock() { return stock; }
    public int orders() { return orders; }
}
