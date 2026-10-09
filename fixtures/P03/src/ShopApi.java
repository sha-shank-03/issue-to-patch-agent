package fixture;

/** Authored fictional semantic-defect fixture. */
public final class ShopApi {
    private record Row(int id, int createdAt) {}
    private final java.util.List<Row> rows = java.util.List.of(new Row(4,20), new Row(3,10), new Row(1,10), new Row(2,20), new Row(6,30), new Row(5,30));
    public java.util.List<Integer> page(int page, int size) {
        if (page < 0 || size < 1 || size > 100) throw new IllegalArgumentException("invalid page");
        long offset = (long) page * size;
        if (offset >= rows.size()) return java.util.List.of();
        int from = (int) offset, to = Math.min(from + size, rows.size());
        java.util.List<Row> sorted = new java.util.ArrayList<>(rows);
        sorted.sort(java.util.Comparator.comparingInt(Row::createdAt));
        return sorted.subList(from, to).stream().map(Row::id).toList();
    }
}
